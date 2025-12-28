from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404

import os


from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import User, Realtor, Commission

from django.contrib.auth.forms import (
    PasswordChangeForm,
)  # :contentReference[oaicite:0]{index=0}
from django.contrib.auth import update_session_auth_hash

from django.db.models import Q, F
from django.db.models import Value
from django.db.models.functions import Concat


from .models import (
    Property,
    PropertySale,
    Payment,
    General,
    Plot,
    SecretaryAdmin,
)
from django.http import JsonResponse
from decimal import Decimal, InvalidOperation
from django.utils import timezone

from django.db.models import Sum  # Add this import

from django.core.paginator import Paginator


from django.contrib.auth.forms import PasswordResetForm

# from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.db.models.query_utils import Q
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.core.mail import send_mail, BadHeaderError
from django.core.mail import send_mass_mail
from django.http import HttpResponse

# from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm

# Get sales data by month for the current year
from django.db.models.functions import TruncMonth
from datetime import datetime
import json

from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_control
from django.conf import settings
# import boto3
# from botocore.exceptions import ClientError

import decimal

# views.py
from django.http import HttpResponse, Http404
import requests

from django.urls import reverse
import logging
from django.views.decorators.csrf import csrf_protect
from django.utils.html import strip_tags

from .helper import admin_required, admin_or_secretary_required, secretary_required
from django.db import transaction
import string
import random


logger = logging.getLogger(__name__)


# User = get_user_model()


# Create your views here.
def robots_txt(request):
    return HttpResponse("User-agent: *\nDisallow:", content_type="text/plain")


def realtors_check(request):
    """
    View for realtors to search for their profile using a query string.
    Supports search by referral code, first name, full name, phone or email.
    """
    search_performed = False
    realtor = None
    commissions = None
    direct_referrals = None

    # Read search_query from the template input (name="search_query")
    search_query = request.GET.get('search_query', '').strip()

    if search_query:
        search_performed = True

        # Search directly against the individual fields
        matches = Realtor.objects.filter(
            Q(referral_code__iexact=search_query) |  # Exact match for referral code
            Q(first_name__icontains=search_query) |  # Case-insensitive partial matches for names
            Q(last_name__icontains=search_query) |
            Q(phone__icontains=search_query) |       # Partial match for phone
            Q(email__icontains=search_query)         # Partial match for email
        ).order_by('-created_at')

        # If no matches found, try splitting the search query for full name search
        if not matches.exists() and ' ' in search_query:
            name_parts = search_query.split()
            name_queries = Q()
            for part in name_parts:
                name_queries |= Q(first_name__icontains=part) | Q(last_name__icontains=part)
            matches = Realtor.objects.filter(name_queries).order_by('-created_at')

        if matches.exists():
            # Pick the most recent match if multiple
            realtor = matches.first()

            # Get commissions and direct referrals for the found realtor
            commissions = Commission.objects.filter(realtor=realtor).order_by('-created_at')
            direct_referrals = Realtor.objects.filter(sponsor=realtor).order_by('-created_at')
        else:
            messages.error(request, f"No realtor found matching: {search_query}")

    context = {
        'realtor': realtor,
        'search_performed': search_performed,
        'commissions': commissions,
        'direct_referrals': direct_referrals,
        'search_query': search_query,
    }

    return render(request, 'estate/realtors_check.html', context)


# ====================================ADMIN INTERFACE================================================================================
# ===================================                =================================================================================


@login_required
@admin_required
def userhome(request):
    # Calculate total sales amount (in Naira)
    total_sales_amount = PropertySale.objects.aggregate(Sum("selling_price"))[
        "selling_price__sum"
    ] or Decimal("0")

    # Count number of property sales transactions
    total_sales_count = PropertySale.objects.count()

    # Count total realtors
    total_realtors = Realtor.objects.count()

    # Count paid commissions
    paid_commissions_count = Commission.objects.filter(is_paid=True).count()

    # Count unpaid commissions
    unpaid_commissions_count = Commission.objects.filter(is_paid=False).count()

    # Calculate total paid commissions amount
    total_paid_commissions = Commission.objects.filter(is_paid=True).aggregate(
        Sum("amount")
    )["amount__sum"] or Decimal("0")

    # Calculate total unpaid commissions amount
    total_unpaid_commissions = Commission.objects.filter(is_paid=False).aggregate(
        Sum("amount")
    )["amount__sum"] or Decimal("0")

    # Format the numbers with appropriate suffixes
    def format_number(number):
        if number >= 1_000_000_000:  # Billions
            return f"₦{number / 1_000_000_000:.1f}B"
        elif number >= 1_000_000:  # Millions
            return f"₦{number / 1_000_000:.1f}M"
        elif number >= 1_000:  # Thousands
            return f"₦{number / 1_000:.1f}K"
        else:
            return f"₦{number:.0f}"

    # Get sales data by month for the current year
    current_year = datetime.now().year

    # Monthly sales data
    monthly_sales = (
        PropertySale.objects.filter(created_at__year=current_year)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Sum("selling_price"))
        .order_by("month")
    )

    # Monthly commissions data
    monthly_commissions = (
        Commission.objects.filter(created_at__year=current_year)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    # Prepare chart data
    months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    sales_data = [0] * 12
    commission_data = [0] * 12

    for entry in monthly_sales:
        month_idx = entry["month"].month - 1  # Convert to 0-based index
        sales_data[month_idx] = float(entry["total"])

    for entry in monthly_commissions:
        month_idx = entry["month"].month - 1  # Convert to 0-based index
        commission_data[month_idx] = float(entry["total"])

    # Get top 5 realtors by commission earned
    top_realtors = (
        Realtor.objects.annotate(commission_earned=Sum("commissions__amount"))
        .exclude(commission_earned=None)
        .order_by("-commission_earned")[:5]
    )

    top_realtors_data = []
    for realtor in top_realtors:
        top_realtors_data.append(
            {
                "name": realtor.full_name,
                "commission": float(realtor.commission_earned or 0),
            }
        )

    # Format data for JavaScript
    chart_data = {
        "months": months,
        "sales": sales_data,
        "commissions": commission_data,
        "topRealtors": top_realtors_data,
    }

    context = {
        "total_sales_amount": format_number(total_sales_amount),
        "total_sales_count": total_sales_count,
        "total_realtors": total_realtors,
        "paid_commissions_count": paid_commissions_count,
        "unpaid_commissions_count": unpaid_commissions_count,
        "total_paid_commissions": format_number(total_paid_commissions),
        "total_unpaid_commissions": format_number(total_unpaid_commissions),
        "total_paid_commissions_raw": float(total_paid_commissions),  # Raw value for calculations
        "total_unpaid_commissions_raw": float(total_unpaid_commissions),  # Raw value for calculations
        "chart_data": json.dumps(chart_data),
    }

    return render(request, "user/home.html", context)


@login_required
@admin_required
def profile(request):
    user = request.user
    password_form = PasswordChangeForm(user=user)

    if request.method == "POST":
        # PROFILE UPDATE
        if "profile_submit" in request.POST:
            user.first_name = request.POST.get("first_name", user.first_name)
            user.last_name = request.POST.get("last_name", user.last_name)
            profile_image = request.FILES.get("profile_image")
            if profile_image:
                user.image = profile_image
            user.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("profile")

        # PASSWORD CHANGE
        elif "password_submit" in request.POST:
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user = (
                    password_form.save()
                )  # hashes & saves new password :contentReference[oaicite:9]{index=9}
                update_session_auth_hash(
                    request, user
                )  # preserve session :contentReference[oaicite:10]{index=10}
                messages.success(request, "Password changed successfully.")
                return redirect("profile")
            else:
                messages.error(request, "Please correct the errors below.")

    return render(
        request,
        "user/profile.html",
        {
            "user": user,
            "password_form": password_form,
        },
    )


def signin(request):
    if not request.user.is_authenticated and request.GET.get("next"):
        messages.info(request, "You need to login to access this page.")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # user = authenticate(request, username=username, password=password)
        user = None

        if "@" in username:  # Email login case
            user = authenticate(
                request,
                username=User.objects.filter(email=username).first().username,
                password=password,
            )
        else:  # Username login case
            user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Login Successful!")

            # Check if user is a secretary admin
            try:
                secretary = SecretaryAdmin.objects.get(user=user)
                if secretary.is_active:
                    return redirect("secretary_dashboard")
                else:
                    messages.error(
                        request, "Your secretary account is currently inactive."
                    )
                    return redirect("signin")
            except SecretaryAdmin.DoesNotExist:
                # Regular admin user
                return redirect("user")
        else:
            messages.error(request, "Invalid username or password")
    return render(request, "user/signin.html")


@login_required
def signout(request):
    logout(request)
    messages.success(request, "logout successful")
    return redirect("signin")


@login_required
def realtors_page(request):
    """
    View for displaying realtors with search functionality and pagination.
    Allows searching by name, referral code, phone number, etc.
    """
    # Get search parameter from the request
    search_query = request.GET.get("search", "")

    # Start with all realtors
    realtors = Realtor.objects.all()

    # Apply search filter if a search query is provided
    if search_query:
        realtors = realtors.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(referral_code__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(email__icontains=search_query)
        )

    # Order the results
    realtors = realtors.order_by("first_name", "last_name")

    # Paginate the results
    paginator = Paginator(realtors, 20)  # Show 10 realtors per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "realtors": page_obj,  # Pass the paginated object instead of the full queryset
        "search_query": search_query,  # Pass the search query back to the template
        "page_obj": page_obj,  # Pagination object for creating pagination controls
        "paginator": paginator,  # The paginator object itself
    }

    return render(request, "user/realtors_page.html", context)


@login_required
def create_realtor(request):
    """View for creating a new realtor profile"""
    if request.method == "POST":
        # Extract form data
        first_name = request.POST.get("firstname")
        last_name = request.POST.get("lastname")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        account_number = request.POST.get("accnumber")
        bank_name = request.POST.get("bankname")
        account_name = request.POST.get("accountname")
        address = request.POST.get("address")
        country = request.POST.get("country")
        sponsor_code = request.POST.get("sponsorcode", "").strip()
        
        # Use default sponsor code if not provided
        if not sponsor_code:
            sponsor_code = "29496781"

        # Create new realtor instance
        realtor = Realtor(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            account_number=account_number,
            bank_name=bank_name,
            account_name=account_name,
            address=address,
            country=country,
            sponsor_code=sponsor_code,
        )

        # Handle image upload
        if "image" in request.FILES:
            realtor.image = request.FILES["image"]

        # Save the realtor (this will also generate the referral code)
        try:
            with transaction.atomic():
                realtor.save()

                # CRITICAL: Verify ID was assigned
                if not realtor.pk:
                    raise ValueError("Realtor was saved but did not receive an ID. This should never happen.")

                # Refresh from database to ensure all fields are properly set
                realtor.refresh_from_db()

            # Send welcome email immediately after successful creation
            try:
                # Construct referral link
                referral_link = f"{request.build_absolute_uri('/').rstrip('/')}/realtor/register/{realtor.referral_code}/"

                # Email subject
                subject = "Welcome to Triple D Big Dream Homes - Your Registration is Complete!"

                # Email message
                message = f"""
Dear {first_name} {last_name},

🎉 Welcome to Triple D Big Dream Homes! 🎉

Congratulations! Your registration as a Professional Realtor has been successfully completed.

Here are your important details:

📋 ACCOUNT INFORMATION:
• Name: {first_name} {last_name}
• Email: {email}
• Phone: {phone}
• Country: {country}

🔗 YOUR REFERRAL DETAILS:
• Your Referral Code: {realtor.referral_code}
• Your Referral Link: {referral_link}

💡 HOW TO USE YOUR REFERRAL:
Share your referral link with potential realtors to earn commissions when they register and make sales. Your unique referral code ({realtor.referral_code}) will automatically be applied when someone uses your link.

🚀 NEXT STEPS:
1. Save your referral code and link in a safe place
2. Start sharing your referral link to grow your network
3. Contact our support team if you have any questions

Thank you for joining Triple D Big Dream Homes. We're excited to have you as part of our professional realtor community!

Best regards,
The Triple D Big Dream Homes Team

---
This is an automated message. Please do not reply to this email.
For support, contact us through our official channels.
                """.strip()

                # Send the email
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )

                logger.info(f"Welcome email sent successfully to {email}")
                messages.success(
                    request,
                    f"Realtor profile created successfully! Referral code: {realtor.referral_code}. A welcome email has been sent to {email}.",
                )

            except Exception as email_error:
                logger.error(
                    f"Failed to send welcome email to {email}: {str(email_error)}"
                )
                messages.success(
                    request,
                    f"Realtor profile created successfully! Referral code: {realtor.referral_code}",
                )
                messages.warning(
                    request,
                    "However, there was an issue sending the welcome email. Please contact support for referral details.",
                )

            return redirect(
                "realtor_detail", id=realtor.id
            )  # Redirect to detail view or appropriate page

        except Exception as e:
            logger.error(f"Error creating realtor profile for {email}: {str(e)}")
            messages.error(request, f"Error creating realtor profile: {str(e)}")

    # For GET requests, just render the form
    return render(request, "user/create_realtor.html")


@login_required
def realtor_detail(request, id):
    """
    Display detailed information about a realtor, including their commissions,
    direct referrals, and second-level referrals.
    """

    realtor = get_object_or_404(Realtor, id=id)

    # Get commissions for this realtor
    commissions = Commission.objects.filter(realtor=realtor).order_by("-created_at")

    # Get direct referrals (realtors who used this realtor's referral code)
    direct_referrals = Realtor.objects.filter(sponsor=realtor).order_by("-created_at")

    # Get second-level referrals (realtors referred by this realtor's direct referrals)
    secondary_referrals = Realtor.objects.filter(sponsor__sponsor=realtor).order_by(
        "-created_at"
    )

    context = {
        "realtor": realtor,
        "commissions": commissions,
        "direct_referrals": direct_referrals,
        "secondary_referrals": secondary_referrals,
    }

    return render(request, "user/realtor_detail.html", context)


@login_required
@admin_required
def edit_realtor(request, id):
    """View for editing an existing realtor profile"""
    realtor = get_object_or_404(Realtor, id=id)

    if request.method == "POST":  ####2218159080
        # Extract form data
        realtor.first_name = request.POST.get("firstname")
        realtor.last_name = request.POST.get("lastname")
        realtor.email = request.POST.get("email")
        realtor.phone = request.POST.get("phone")
        realtor.account_number = request.POST.get("accnumber")
        realtor.bank_name = request.POST.get("bankname")
        realtor.account_name = request.POST.get("accname")
        realtor.address = request.POST.get("address")
        realtor.country = request.POST.get("country")

        # Handle status field if your model has it
        if "status" in request.POST:
            realtor.status = request.POST.get("status")

        # Handle bio field if your model has it
        if "bio" in request.POST:
            realtor.bio = request.POST.get("bio")

        # Handle image upload
        if "image" in request.FILES:
            # New image uploaded
            realtor.image = request.FILES["image"]
        elif "remove_image" in request.POST:
            # Remove existing image
            realtor.image = None

        realtor.save()
        messages.success(request, "Realtor information updated successfully.")
        return redirect("realtor_detail", id=realtor.id)

    return render(request, "user/edit_realtor.html", {"realtor": realtor})


@login_required
@admin_required
def delete_realtor(request, id):
    """
    View to delete a realtor after confirmation
    """
    # Get the realtor object or return 404
    realtor = get_object_or_404(Realtor, id=id)

    # Check if there are commissions associated with this realtor
    has_commissions = Commission.objects.filter(realtor=realtor).exists()

    # Check if there are property sales associated with this realtor
    has_sales = PropertySale.objects.filter(realtor=realtor).exists()

    # If this is a POST request, delete the realtor
    if request.method == "POST":
        # Check if realtor can be safely deleted
        if has_commissions or has_sales:
            messages.warning(
                request,
                f"Cannot delete '{realtor.first_name} {realtor.last_name}' because they have associated commissions or sales records.",
            )
        else:
            realtor_name = f"{realtor.first_name} {realtor.last_name}"  # Store name before deletion
            realtor.delete()
            messages.success(
                request, f"Realtor '{realtor_name}' has been deleted successfully."
            )

    # Redirect back to the realtors list
    return redirect("realtors_page")


# @permission_required('realtors.can_pay_commission', raise_exception=True)
@login_required
@admin_required
def pay_all_commissions(request, realtor_id):
    """Mark all unpaid commissions for a realtor as paid"""
    if request.method == "POST":
        realtor = get_object_or_404(Realtor, pk=realtor_id)
        unpaid_commissions = Commission.objects.filter(realtor=realtor, is_paid=False)

        count = 0
        for commission in unpaid_commissions:
            commission.mark_as_paid()
            count += 1

        if count > 0:
            messages.success(
                request,
                f"{count} commissions totaling ${realtor.unpaid_commission} have been marked as paid.",
            )
        else:
            messages.info(request, "There were no unpaid commissions to mark as paid.")

    return redirect("realtor_detail", id=realtor_id)


@login_required
@admin_required
def register_property(request):
    """View to register a new property"""
    # Get all states from Property model choices
    states = Property._meta.get_field("location").choices

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        location = request.POST.get("location")
        address = request.POST.get("address")
        number_of_plots = request.POST.get("number_of_plots")

        # Create new property
        with transaction.atomic():
            status = request.POST.get("status", "available")
            property = Property.objects.create(
                name=name, description=description, location=location, address=address, status=status
            )

            # CRITICAL: Verify ID was assigned
            if not property.pk:
                raise ValueError("Property was created but did not receive an ID. This should never happen.")
            
            # Create plots if requested
            plot_count = 0
            if number_of_plots:
                try:
                    count = int(number_of_plots)
                    # Use bulk_create for efficiency if many plots
                    plots_to_create = [
                        Plot(property=property, number=f"Plot {i}")
                        for i in range(1, count + 1)
                    ]
                    Plot.objects.bulk_create(plots_to_create)
                    plot_count = count
                except (ValueError, TypeError):
                    pass # Silently continue if plot count is invalid

        if plot_count > 0:
            msg = f'Property "{name}" has been registered successfully with {plot_count} plots!'
        else:
            msg = f'Property "{name}" has been registered successfully!'
            
        messages.success(request, msg)
        return redirect("property_list")

    return render(request, "user/register_property.html", {"states": states})


@login_required
@admin_required
def property_list(request):
    """View to display all properties"""
    properties = Property.objects.all().order_by("-created_at")

    return render(request, "user/property_list.html", {"properties": properties})


@login_required
@admin_or_secretary_required
def property_detail(request, property_id):
    """View to display property details with a more comprehensive interface"""
    property = get_object_or_404(Property, id=property_id)

    # Get all sales for this property - use property_item instead of property
    sales = PropertySale.objects.filter(property_item=property).order_by("-created_at")
    
    # Get all plots for this property with their associated sales
    plots = property.plots.all().prefetch_related('sales').order_by('id')

    context = {"property": property, "sales": sales, "plots": plots}

    return render(request, "user/property_detail.html", context)


@login_required
@admin_required
def edit_property(request, property_id):
    """View for editing an existing property"""
    property = get_object_or_404(Property, id=property_id)

    # Get all states from Property model choices for the form dropdown
    states = Property._meta.get_field("location").choices

    if request.method == "POST":
        action = request.POST.get("action", "update_info")
        
        if action == "update_info":
            # Extract form data
            property.name = request.POST.get("name")
            property.description = request.POST.get("description")
            property.location = request.POST.get("location")
            property.address = request.POST.get("address")

            # Handle status field if your model has it
            if "status" in request.POST:
                property.status = request.POST.get("status")

            # Handle image upload
            if "image" in request.FILES:
                # New image uploaded
                property.image = request.FILES["image"]
            elif "remove_image" in request.POST:
                # Remove existing image
                property.image = None

            property.save()
            messages.success(request, "Property information updated successfully.")
            return redirect("edit_property", property_id=property.id)
            
        elif action == "add_plots":
            try:
                count = int(request.POST.get("number_of_plots", 0))
                if count > 0:
                    current_plots_count = property.plots.count()
                    
                    # More robust numbering: find the highest current number if it's numeric
                    highest_num = 0
                    for p in property.plots.all():
                        try:
                            num_part = p.number.replace("Plot ", "").strip()
                            highest_num = max(highest_num, int(num_part))
                        except (ValueError, TypeError):
                            pass
                    
                    if highest_num == 0:
                        highest_num = current_plots_count

                    plots_to_create = [
                        Plot(property=property, number=f"Plot {i}")
                        for i in range(highest_num + 1, highest_num + count + 1)
                    ]
                    Plot.objects.bulk_create(plots_to_create)
                    messages.success(request, f"{count} new plots added successfully.")
            except (ValueError, TypeError):
                messages.error(request, "Invalid number of plots.")
            return redirect("edit_property", property_id=property.id)

    plots = property.plots.all().prefetch_related('sales').order_by('id')
    return render(
        request, "user/edit_property.html", {"property": property, "states": states, "plots": plots}
    )


@login_required
def ajax_get_plots(request):
    property_id = request.GET.get('property_id')
    if not property_id:
        return JsonResponse({'success': False, 'error': 'No property ID provided'})
    
    property = get_object_or_404(Property, id=property_id)
    plots = property.plots.all().order_by('id').values('id', 'number', 'is_taken')
    
    return JsonResponse({
        'success': True,
        'plots': list(plots)
    })


@login_required
@admin_required
def ajax_toggle_plot_status(request):
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permission denied. Only Chief Admin can toggle plot status.'})
        
    if request.method == "POST":
        plot_id = request.POST.get('plot_id')
        plot = get_object_or_404(Plot, id=plot_id)
        plot.is_taken = not plot.is_taken
        plot.save()
        return JsonResponse({'success': True, 'is_taken': plot.is_taken})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
@admin_required
def delete_property(request, property_id):
    """
    View to delete a property after confirmation
    """
    # Get the property object or return 404
    property_obj = get_object_or_404(Property, id=property_id)

    # Remove the user check for now, or replace with appropriate check
    # if property_obj.user != request.user:
    #     messages.error(request, "You don't have permission to delete this property.")
    #     return redirect('property_list')

    # Check if there are any sales associated with this property
    if property_obj.sales.exists():
        messages.warning(
            request,
            f"Cannot delete '{property_obj.name}' because it has associated sales records.",
        )
        return redirect("property_list")

    # If this is a POST request, delete the property
    if request.method == "POST":
        property_name = property_obj.name  # Store name before deletion
        property_obj.delete()
        messages.success(
            request, f"Property '{property_name}' has been deleted successfully."
        )

    # Redirect back to the property list
    return redirect("property_list")


# Your existing view stays the same
@login_required
def property_sales_list(request):
    """View to display all property sales"""
    all_sales = PropertySale.objects.select_related('created_by', 'property_item', 'realtor').all().order_by("-created_at")
    paginator = Paginator(all_sales, 20)  # 20 sales per page
    page_number = request.GET.get("page", 1)  # get ?page= from URL, default to 1
    sales = paginator.get_page(page_number)

    return render(request, "user/property_sales_list.html", {"sales": sales})


@login_required
@admin_required
def send_client_email(request, sale_id):
    """Send email to client based on development status"""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method"})

    try:
        sale = get_object_or_404(PropertySale, id=sale_id)
        email_type = request.POST.get("email_type")  # 'reminder' or 'revocation'

        if not sale.client_email:
            return JsonResponse(
                {"success": False, "message": "Client email not available"}
            )

        # Determine email content based on type and status
        if email_type == "reminder":
            subject = "Reminder on Plot Development Timeline and Consequences of Non-Compliance"
            template_name = "emails/development_reminder.html"
        elif email_type == "revocation":
            subject = "NOTICE OF PLOT REVOCATION FOR NON-DEVELOPMENT"
            template_name = "emails/plot_revocation.html"
        else:
            return JsonResponse({"success": False, "message": "Invalid email type"})

        # Calculate development duration (you may need to adjust this based on your business logic)
        development_duration = "3 years"  # Default, you can make this dynamic

        # Build absolute URL for logo (required for email clients)
        logo_url = request.build_absolute_uri('/static/user/images/tripledlogo.jpeg')

        # Prepare context for email template
        context = {
            "client_name": sale.client_name,
            "property_name": sale.property_item.name,
            "expiry_date": sale.plot_development_expiry_date.strftime("%B %d, %Y")
            if sale.plot_development_expiry_date
            else "Not Set",
            "development_duration": development_duration,
            "reference_number": sale.reference_number,
            "current_date": datetime.now().strftime("%B %d, %Y"),
            "logo_url": logo_url,  # Absolute URL for logo in emails
        }

        # Render email content
        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)

        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[sale.client_email],
            html_message=html_message,
            fail_silently=False,
        )

        # Log the email sent
        logger.info(
            f"Email sent to {sale.client_email} for sale {sale.reference_number}"
        )

        return JsonResponse(
            {
                "success": True,
                "message": f"{email_type.capitalize()} email sent successfully to {sale.client_name}",
            }
        )

    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return JsonResponse(
            {"success": False, "message": f"Error sending email: {str(e)}"}
        )


# ADD THIS NEW VIEW
@login_required
@admin_required
def mark_property_developed(request, sale_id):
    """Mark a property sale as developed"""
    sale = get_object_or_404(PropertySale, id=sale_id)

    if request.method == "POST":
        # Toggle the development status
        sale.is_developed = not sale.is_developed
        sale.save()

        status = "developed" if sale.is_developed else "not developed"
        messages.success(
            request, f"Property {sale.reference_number} marked as {status}."
        )

        # If it's an AJAX request, return JSON response
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": True,
                    "is_developed": sale.is_developed,
                    "status": sale.development_status_display,
                    "status_class": sale.development_status_class,
                }
            )

        return redirect("property_sale_detail", id=sale_id)

    return redirect("property_sale_detail", id=sale_id)


@login_required
@admin_required
@require_http_methods(["POST"])
def send_private_email(request, sale_id):
    try:
        # Get the property sale
        sale = PropertySale.objects.get(id=sale_id)

        # Check if client has email
        if not sale.client_email:
            return JsonResponse(
                {"success": False, "error": "Client email address not found."}
            )

        # Get form data
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()

        if not subject or not message:
            return JsonResponse(
                {"success": False, "error": "Subject and message are required."}
            )

        # Prepare email content
        email_message = f"""
Dear {sale.client_name},

{message}

Best regards,
Triple D Big Dream Homes ADMIN

Head office address.
No 66 Shehu RD Lakeview estate 
phase 2 Ago palace way Amuwo odofin Lagos.

Branches addresses.

Suit 1 Adonai Complex
No 2 Onyiuke  Street,
Off Edimbo Road, Ogui New Layout, Enugu

Shop B8/B11, Block C, Millennium Plaza, 
Opp. ABS, Behind UBA,Aroma, 
Enugu-Onitsha Express road, Awka, Anambra State.



Phone: +2348033035633
Email: info@tripledhomes.com.ng

---
This email is regarding your property purchase:
Reference: {sale.reference_number}
Property: {sale.property_item.name}
        """

        # Send email
        send_mail(
            subject=subject,
            message=email_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[sale.client_email],
            fail_silently=False,
        )

        logger.info(
            f"Private email sent to {sale.client_email} for sale {sale.reference_number}"
        )

        return JsonResponse({"success": True, "message": "Email sent successfully!"})

    except PropertySale.DoesNotExist:
        return JsonResponse({"success": False, "error": "Property sale not found."})
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return JsonResponse(
            {"success": False, "error": "Failed to send email. Please try again."}
        )


@login_required
@admin_required
def bulk_email(request):
    """Display bulk email page with all sales records"""

    # Get all sales records - no filtering or pagination
    sales = PropertySale.objects.select_related("property_item", "realtor", "created_by").order_by(
        "-created_at"
    )

    # Get all properties for the estate filter dropdown
    properties = Property.objects.all().order_by("name")

    context = {
        "sales": sales,
        "properties": properties,
    }

    return render(request, "user/bulk_email.html", context)


@login_required
@admin_required
@require_http_methods(["POST"])
def send_bulk_email(request):
    """Send bulk emails to selected clients"""
    try:
        # Get form data
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()
        client_ids_json = request.POST.get("client_ids", "[]")

        if not subject or not message:
            return JsonResponse(
                {"success": False, "error": "Subject and message are required."}
            )

        # Parse client IDs
        try:
            client_ids = json.loads(client_ids_json)
        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "error": "Invalid client selection."}
            )

        if not client_ids:
            return JsonResponse(
                {"success": False, "error": "Please select at least one client."}
            )

        # Get selected sales - only those with valid emails
        sales = PropertySale.objects.filter(
            id__in=client_ids, client_email__isnull=False, client_email__gt=""
        ).select_related("property_item")

        if not sales.exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": "No valid email addresses found for selected clients.",
                }
            )

        sent_count = 0
        failed_emails = []

        # Send emails
        for sale in sales:
            try:
                # Personalize the message
                personalized_message = f"""Dear {sale.client_name},

{message}

Best regards,
Triple D Big Dream Homes ADMIN

Head office address.
No 66 Shehu RD Lakeview estate 
phase 2 Ago palace way Amuwo odofin Lagos.

Branches addresses.

Suit 1 Adonai Complex
No 2 Onyiuke  Street,
Off Edimbo Road, Ogui New Layout, Enugu

Shop B8/B11, Block C, Millennium Plaza, 
Opp. ABS, Behind UBA,Aroma, 
Enugu-Onitsha Express road, Awka, Anambra State.



Phone: +2348033035633
Email: info@tripledhomes.com.ng

---
Property Details:
Reference: {sale.reference_number}
Estate: {sale.property_item.name}
Property Type: {sale.get_property_type_display()}
                """

                # Send email
                send_mail(
                    subject=subject,
                    message=personalized_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[sale.client_email],
                    fail_silently=False,
                )

                sent_count += 1

            except Exception as e:
                failed_emails.append(sale.client_email)
                # Log the error if you have logging configured
                print(f"Failed to send email to {sale.client_email}: {str(e)}")

        # Prepare response
        if sent_count > 0:
            response_data = {
                "success": True,
                "sent_count": sent_count,
                "message": f"Successfully sent {sent_count} emails.",
            }

            if failed_emails:
                response_data["warning"] = (
                    f"Failed to send to: {', '.join(failed_emails)}"
                )

            return JsonResponse(response_data)
        else:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Failed to send any emails. Please check the email configuration.",
                }
            )

    except Exception as e:
        print(f"Error in bulk email sending: {str(e)}")
        return JsonResponse(
            {
                "success": False,
                "error": "An error occurred while sending emails. Please try again.",
            }
        )


@login_required
@admin_required
def bulk_email_realtors(request):
    """Display bulk email page with all realtors"""
    
    # Get all realtors
    realtors = Realtor.objects.all().order_by("-created_at")
    
    context = {
        "realtors": realtors,
    }
    
    return render(request, "user/bulk_email_realtors.html", context)


@login_required
@admin_required
@require_http_methods(["POST"])
def send_bulk_email_realtors(request):
    """Send bulk emails to selected realtors"""
    try:
        # Get form data
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()
        realtor_ids_json = request.POST.get("realtor_ids", "[]")
        
        if not subject or not message:
            return JsonResponse(
                {"success": False, "error": "Subject and message are required."}
            )
        
        # Parse realtor IDs
        try:
            realtor_ids = json.loads(realtor_ids_json)
        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "error": "Invalid realtor selection."}
            )
        
        if not realtor_ids:
            return JsonResponse(
                {"success": False, "error": "Please select at least one realtor."}
            )
        
        # Get selected realtors - only those with valid emails
        realtors = Realtor.objects.filter(
            id__in=realtor_ids, email__isnull=False, email__gt=""
        )
        
        if not realtors.exists():
            return JsonResponse(
                {
                    "success": False,
                    "error": "No valid email addresses found for selected realtors.",
                }
            )
        
        sent_count = 0
        failed_emails = []
        
        # Send emails
        for realtor in realtors:
            try:
                # Personalize the message
                personalized_message = f"""Dear {realtor.full_name},

{message}

Best regards,
Triple D Big Dream Homes ADMIN

Head office address.
No 66 Shehu RD Lakeview estate 
phase 2 Ago palace way Amuwo odofin Lagos.

Branches addresses.

Suit 1 Adonai Complex
No 2 Onyiuke  Street,
Off Edimbo Road, Ogui New Layout, Enugu

Shop B8/B11, Block C, Millennium Plaza, 
Opp. ABS, Behind UBA,Aroma, 
Enugu-Onitsha Express road, Awka, Anambra State.

Phone: +2348033035633
Email: info@tripledhomes.com.ng

---
Realtor Details:
Name: {realtor.full_name}
Email: {realtor.email}
Phone: {realtor.phone or 'Not provided'}
Status: {realtor.status_display}
Referral Code: {realtor.referral_code}
                """
                
                # Send email
                send_mail(
                    subject=subject,
                    message=personalized_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[realtor.email],
                    fail_silently=False,
                )
                
                sent_count += 1
                
            except Exception as e:
                failed_emails.append(realtor.email)
                # Log the error if you have logging configured
                print(f"Failed to send email to {realtor.email}: {str(e)}")
        
        # Prepare response
        if sent_count > 0:
            response_data = {
                "success": True,
                "sent_count": sent_count,
                "message": f"Successfully sent {sent_count} emails.",
            }
            
            if failed_emails:
                response_data["warning"] = (
                    f"Failed to send to: {', '.join(failed_emails)}"
                )
            
            return JsonResponse(response_data)
        else:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Failed to send emails. Please try again.",
                }
            )
            
    except Exception as e:
        logger.error(f"Error in send_bulk_email_realtors: {str(e)}")
        return JsonResponse(
            {"success": False, "error": f"An error occurred: {str(e)}"}
        )


@login_required
def register_property_sale(request):  # with expiry date
    """View to register a new property sale"""
    properties = Property.objects.all().order_by("name")
    # Add select_related to prevent N+1 queries and relationship issues
    realtors = (
        Realtor.objects.select_related("sponsor", "sponsor__sponsor")
        .all()
        .order_by("first_name", "last_name")
    )

    if request.method == "POST":
        try:
            # Extract basic property information
            property_id = request.POST.get("property")
            description = request.POST.get("description")
            property_type = request.POST.get("property_type")
            quantity = request.POST.get("quantity")
            selected_plots_ids = request.POST.getlist("selected_plots")

            # Extract client information
            client_name = request.POST.get("client_name")
            client_address = request.POST.get("client_address")
            client_phone = request.POST.get("client_phone")
            client_email = request.POST.get("client_email")
            marital_status = request.POST.get("marital_status")
            spouse_name = request.POST.get("spouse_name", "")
            spouse_phone = request.POST.get("spouse_phone", "")
            # Add after client_email extraction
            client_picture = request.FILES.get("client_picture")

            # Extract client identification
            id_type = request.POST.get("id_type")
            id_number = request.POST.get("id_number")

            # Extract plot development timeline (NEW FIELDS)
            plot_development_start_date_str = request.POST.get(
                "plot_development_start_date"
            )
            plot_development_expiry_date_str = request.POST.get(
                "plot_development_expiry_date"
            )

            # Extract client origin
            lga_of_origin = request.POST.get("lga_of_origin")
            town_of_origin = request.POST.get("town_of_origin")
            state_of_origin = request.POST.get("state_of_origin")

            # Client bank details removed from form - set to None
            bank_name = None
            account_number = None
            account_name = None

            # Extract next of kin information
            next_of_kin_name = request.POST.get("next_of_kin_name")
            next_of_kin_address = request.POST.get("next_of_kin_address")
            next_of_kin_phone = request.POST.get("next_of_kin_phone")

            # Extract financial information
            original_price = request.POST.get("original_price")
            selling_price = request.POST.get("selling_price")
            initial_payment = request.POST.get("initial_payment")
            payment_plan = request.POST.get("payment_plan")
            # Add after selling_price extraction
            discount = request.POST.get("discount")
            payment_date_str = request.POST.get("payment_date")

            # Extract realtor and commission information
            realtor_id = request.POST.get("realtor")
            realtor_commission_percentage = request.POST.get(
                "realtor_commission_percentage"
            )
            sponsor_commission_percentage = request.POST.get(
                "sponsor_commission_percentage"
            )
            upline_commission_percentage = request.POST.get(
                "upline_commission_percentage"
            )

            # Helper function to safely convert to Decimal
            def safe_decimal_conversion(value, field_name, default="0.00"):
                if value is None or str(value).strip() == "":
                    return Decimal(default)
                try:
                    cleaned_value = str(value).strip()
                    return Decimal(cleaned_value)
                except (ValueError, decimal.InvalidOperation) as e:
                    messages.error(
                        request,
                        f'Invalid value for {field_name}: "{value}". Please enter a valid number.',
                    )
                    raise ValueError(f"Invalid {field_name} value")

            # Validate and convert decimal fields
            try:
                original_price_decimal = safe_decimal_conversion(
                    original_price, "original price"
                )
                selling_price_decimal = safe_decimal_conversion(
                    selling_price, "selling price"
                )
                initial_payment_decimal = safe_decimal_conversion(
                    initial_payment, "initial payment", "0.00"
                )
                # Add after initial_payment_decimal conversion
                discount_decimal = safe_decimal_conversion(discount, "discount", "0.00")
                realtor_commission_decimal = safe_decimal_conversion(
                    realtor_commission_percentage,
                    "realtor commission percentage",
                    "0.00",
                )
                sponsor_commission_decimal = safe_decimal_conversion(
                    sponsor_commission_percentage,
                    "sponsor commission percentage",
                    "0.00",
                )
                upline_commission_decimal = safe_decimal_conversion(
                    upline_commission_percentage, "upline commission percentage", "0.00"
                )
            except ValueError:
                # Error message already added by safe_decimal_conversion
                return render(
                    request,
                    "user/register_property_sale.html",
                    {"properties": properties, "realtors": realtors},
                )
            
            # Validate commission percentages
            total_commission_percentage = (
                realtor_commission_decimal + 
                sponsor_commission_decimal + 
                upline_commission_decimal
            )
            
            # Check if total commission exceeds 100%
            if total_commission_percentage > Decimal('100'):
                messages.error(
                    request,
                    f"Total commission percentage ({total_commission_percentage}%) cannot exceed 100%. "
                    f"Please adjust the commission percentages. "
                    f"Current: Realtor {realtor_commission_decimal}%, "
                    f"Sponsor {sponsor_commission_decimal}%, "
                    f"Upline {upline_commission_decimal}%"
                )
                return render(
                    request,
                    "user/register_property_sale.html",
                    {"properties": properties, "realtors": realtors},
                )
            
            # Check if total commission exceeds 30%
            if total_commission_percentage > Decimal('30'):
                messages.warning(
                    request,
                    f"Warning: Total commission percentage ({total_commission_percentage}%) exceeds the recommended 30% limit. "
                    f"This may significantly impact profit margins."
                )
                # Note: We'll still allow it, but show a warning
                # The JavaScript will also show a confirmation dialog

            # Validate quantity
            try:
                quantity_int = int(quantity) if quantity else 1
                if quantity_int <= 0:
                    messages.error(request, "Quantity must be a positive number.")
                    return render(
                        request,
                        "user/register_property_sale.html",
                        {"properties": properties, "realtors": realtors},
                    )
            except (ValueError, TypeError):
                # If quantity is invalid but plots are selected, we'll use the plot count
                if selected_plots_ids:
                    quantity_int = len(selected_plots_ids)
                else:
                    messages.error(
                        request, "Invalid quantity value. Please enter a valid number."
                    )
                    return render(
                        request,
                        "user/register_property_sale.html",
                        {"properties": properties, "realtors": realtors},
                    )

            # Parse and validate plot development dates (NEW VALIDATION LOGIC)
            plot_development_start_date = None
            plot_development_expiry_date = None

            if plot_development_start_date_str:
                try:
                    plot_development_start_date = datetime.strptime(
                        plot_development_start_date_str, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    messages.error(
                        request,
                        "Invalid plot development start date format. Please select a valid date.",
                    )
                    return render(
                        request,
                        "user/register_property_sale.html",
                        {"properties": properties, "realtors": realtors},
                    )

            if plot_development_expiry_date_str:
                try:
                    plot_development_expiry_date = datetime.strptime(
                        plot_development_expiry_date_str, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    messages.error(
                        request,
                        "Invalid plot development expiry date format. Please select a valid date.",
                    )
                    return render(
                        request,
                        "user/register_property_sale.html",
                        {"properties": properties, "realtors": realtors},
                    )

            # Validate that expiry date is after start date (if both are provided)
            if plot_development_start_date and plot_development_expiry_date:
                if plot_development_expiry_date <= plot_development_start_date:
                    messages.error(
                        request,
                        "Plot development expiry date must be after the start date.",
                    )
                    return render(
                        request,
                        "user/register_property_sale.html",
                        {"properties": properties, "realtors": realtors},
                    )

            # Parse and validate payment date (only if initial payment is provided)
            payment_date = None
            if initial_payment_decimal > 0:
                if payment_date_str:
                    try:
                        # Parse the date string from the form (YYYY-MM-DD format)
                        naive_date = datetime.strptime(
                            payment_date_str, "%Y-%m-%d"
                        ).date()

                        # Convert to datetime and make it timezone aware
                        # Set time to current time for the date, or you can set a specific time
                        current_time = timezone.now().time()
                        naive_datetime = datetime.combine(naive_date, current_time)

                        # Make it timezone aware using the current timezone
                        payment_date = timezone.make_aware(naive_datetime)

                    except ValueError:
                        messages.error(
                            request,
                            "Invalid payment date format. Please select a valid date.",
                        )
                        return render(
                            request,
                            "user/register_property_sale.html",
                            {"properties": properties, "realtors": realtors},
                        )
                else:
                    messages.error(
                        request,
                        "Payment date is required when making an initial payment.",
                    )
                    return render(
                        request,
                        "user/register_property_sale.html",
                        {"properties": properties, "realtors": realtors},
                    )

            # Get related objects
            property_obj = get_object_or_404(Property, id=property_id)
            realtor = get_object_or_404(
                Realtor.objects.select_related("sponsor", "sponsor__sponsor"),
                id=realtor_id,
            )

            # Create the property sale object with all fields
            with transaction.atomic():
                property_sale = PropertySale.objects.create(
                    description=description,
                    property_type=property_type,
                    property_item=property_obj,
                    quantity=quantity_int,
                    client_name=client_name,
                    client_address=client_address,
                    client_phone=client_phone,
                    client_email=client_email,
                    marital_status=marital_status,
                    spouse_name=spouse_name,
                    spouse_phone=spouse_phone,
                    # Add to client information section
                    client_picture=client_picture,
                    id_type=id_type,
                    id_number=id_number,
                    # Add the new plot development timeline fields
                    plot_development_start_date=plot_development_start_date,
                    plot_development_expiry_date=plot_development_expiry_date,
                    lga_of_origin=lga_of_origin,
                    town_of_origin=town_of_origin,
                    state_of_origin=state_of_origin,
                    # Client bank details removed from form
                    bank_name=None,
                    account_number=None,
                    account_name=None,
                    next_of_kin_name=next_of_kin_name,
                    next_of_kin_address=next_of_kin_address,
                    next_of_kin_phone=next_of_kin_phone,
                    original_price=original_price_decimal,
                    selling_price=selling_price_decimal,
                    payment_plan=payment_plan,
                    # Add to pricing section
                    discount=discount_decimal,
                    realtor=realtor,
                    realtor_commission_percentage=realtor_commission_decimal,
                    sponsor_commission_percentage=sponsor_commission_decimal,
                    upline_commission_percentage=upline_commission_decimal,
                        created_by=request.user,  # Automatically track who created this sale
                    )

                # Link selected plots and mark them as taken
                if selected_plots_ids:
                    plots = Plot.objects.filter(id__in=selected_plots_ids, property=property_obj)
                    if plots.exists():
                        property_sale.plots.set(plots)
                        plots.update(is_taken=True)
                        # Ensure quantity matches selected plots
                        if property_sale.quantity != plots.count():
                            property_sale.quantity = plots.count()
                            property_sale.save()

                # CRITICAL: Verify ID was assigned
                if not property_sale.pk:
                    raise ValueError("PropertySale was created but did not receive an ID. This should never happen.")
                
                # Refresh from database to ensure all fields are properly set
                property_sale.refresh_from_db()

            # Create initial payment if provided
            if initial_payment_decimal > 0:
                # Update the amount_paid field first
                property_sale.amount_paid = initial_payment_decimal
                property_sale.save()
                
                # CRITICAL: Verify property_sale still has ID after save
                if not property_sale.pk:
                    raise ValueError("PropertySale lost its ID after save. This should never happen.")

                # Create the payment record with the validated payment_date
                payment = Payment.objects.create(
                    property_sale=property_sale,
                    amount=initial_payment_decimal,
                    payment_method="Cash",
                    notes="Initial payment at registration",
                    payment_date=payment_date,
                )
                
                # CRITICAL: Verify payment got an ID
                if not payment.pk:
                    raise ValueError("Payment was created but did not receive an ID. This should never happen.")

            messages.success(
                request,
                f"Property sale registered successfully with reference #{property_sale.reference_number}",
            )
            return redirect("property_sale_detail", id=property_sale.id)

        except Exception as e:
            # Log the error for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in register_property_sale: {str(e)}")

            messages.error(
                request,
                "An error occurred while registering the property sale. Please check your input and try again.",
            )
            return render(
                request,
                "user/register_property_sale.html",
                {"properties": properties, "realtors": realtors},
            )

    # Add today's date for template context
    context = {
        "properties": properties,
        "realtors": realtors,
        "today": timezone.now().date().isoformat(),  # For setting max date in template
    }

    return render(request, "user/register_property_sale.html", context)


@login_required
def property_sale_detail(request, id):
    """View details of a property sale and handle new payments"""
    sale = get_object_or_404(PropertySale.objects.select_related('created_by', 'property_item', 'realtor'), pk=id)
    payments = Payment.objects.filter(property_sale=sale).order_by("-payment_date")

    # Get balance due directly from the model property
    balance_due = sale.balance_due

    # Calculate commissions based on current amount paid
    realtor_commission = (
        sale.amount_paid * Decimal(sale.realtor_commission_percentage)
    ) / Decimal("100")

    sponsor_commission = Decimal("0")
    if sale.realtor.sponsor:
        sponsor_commission = (
            sale.amount_paid * Decimal(sale.sponsor_commission_percentage)
        ) / Decimal("100")

    upline_commission = Decimal("0")
    if sale.realtor.sponsor and sale.realtor.sponsor.sponsor:
        upline_commission = (
            sale.amount_paid * Decimal(sale.upline_commission_percentage)
        ) / Decimal("100")

    # Calculate payment progress percentage using Decimal
    payment_progress_percent = Decimal("0")
    if sale.selling_price > 0:
        payment_progress_percent = (
            sale.amount_paid * Decimal("100")
        ) / sale.selling_price
        # Round to 2 decimal places for display
        payment_progress_percent = payment_progress_percent.quantize(Decimal("0.01"))

    # Handle new payment submission
    if request.method == "POST":
        # Only process if there's still a balance due
        if balance_due > 0:
            try:
                # Ensure we're working with Decimal from the start
                amount = Decimal(request.POST.get("amount", "0"))
                payment_method = request.POST.get("payment_method", "Cash")
                reference = request.POST.get("reference", "")
                notes = request.POST.get("notes", "")
                payment_date_str = request.POST.get("payment_date", "")

                # Validate amount is positive
                if amount <= 0:
                    messages.error(request, "Payment amount must be greater than zero.")
                    return redirect("property_sale_detail", id=sale.id)

                # Ensure amount doesn't exceed balance due
                if amount > balance_due:
                    amount = balance_due
                    # Format amount for display
                    messages.info(
                        request,
                        f"Payment amount adjusted to ₦{amount.quantize(Decimal('0.01'))} to match remaining balance.",
                    )

                # Parse and validate payment date
                payment_date = None
                if payment_date_str:
                    try:
                        # Parse the date string from the form (YYYY-MM-DD format)
                        naive_date = datetime.strptime(
                            payment_date_str, "%Y-%m-%d"
                        ).date()

                        # Convert to datetime and make it timezone aware
                        # Set time to current time for the date, or you can set a specific time
                        current_time = timezone.now().time()
                        naive_datetime = datetime.combine(naive_date, current_time)

                        # Make it timezone aware using the current timezone
                        payment_date = timezone.make_aware(naive_datetime)

                        # Validate that the payment date is not in the future
                        if payment_date > timezone.now():
                            messages.error(
                                request, "Payment date cannot be in the future."
                            )
                            return redirect("property_sale_detail", id=sale.id)

                    except ValueError:
                        messages.error(
                            request,
                            "Invalid payment date format. Please select a valid date.",
                        )
                        return redirect("property_sale_detail", id=sale.id)
                else:
                    messages.error(request, "Payment date is required.")
                    return redirect("property_sale_detail", id=sale.id)

                # Create new payment - this will automatically update the sale's amount_paid in the Payment.save() method
                with transaction.atomic():
                    payment = Payment(
                        property_sale=sale,
                        amount=amount,
                        payment_method=payment_method,
                        reference=reference,
                        notes=notes,
                        payment_date=payment_date,
                    )
                    payment.save()

                    # CRITICAL: Verify ID was assigned
                    if not payment.pk:
                        raise ValueError("Payment was saved but did not receive an ID. This should never happen.")

                    # Refresh the sale object to get updated values after payment
                    sale.refresh_from_db()

                # Recalculate balance due
                balance_due = sale.balance_due

                # Recalculate commissions
                realtor_commission = (
                    sale.amount_paid * Decimal(sale.realtor_commission_percentage)
                ) / Decimal("100")

                sponsor_commission = Decimal("0")
                if sale.realtor.sponsor:
                    sponsor_commission = (
                        sale.amount_paid * Decimal(sale.sponsor_commission_percentage)
                    ) / Decimal("100")

                upline_commission = Decimal("0")
                if sale.realtor.sponsor and sale.realtor.sponsor.sponsor:
                    upline_commission = (
                        sale.amount_paid * Decimal(sale.upline_commission_percentage)
                    ) / Decimal("100")

                # Recalculate payment progress
                if sale.selling_price > 0:
                    payment_progress_percent = (
                        sale.amount_paid * Decimal("100")
                    ) / sale.selling_price
                    payment_progress_percent = payment_progress_percent.quantize(
                        Decimal("0.01")
                    )

                # Format the payment date for display in the success message
                formatted_date = payment_date.strftime("%B %d, %Y")
                messages.success(
                    request,
                    f"Payment of ₦{amount.quantize(Decimal('0.01'))} for {formatted_date} successfully recorded!",
                )

                # Check if payment is now complete
                if balance_due <= 0:
                    messages.success(
                        request,
                        "Congratulations! This property has been fully paid for.",
                    )

            except (ValueError, InvalidOperation) as e:
                messages.error(
                    request,
                    "Invalid payment information. Please check your inputs and try again.",
                )
        else:
            messages.info(request, "This property has already been fully paid for.")

        # Redirect to avoid form resubmission
        return redirect("property_sale_detail", id=sale.id)

    context = {
        "sale": sale,
        "payments": payments,
        "realtor_commission": realtor_commission.quantize(Decimal("0.01")),
        "sponsor_commission": sponsor_commission.quantize(Decimal("0.01")),
        "upline_commission": upline_commission.quantize(Decimal("0.01")),
        "payment_progress_percent": payment_progress_percent,
        "balance_due": balance_due.quantize(Decimal("0.01")),
        "today": timezone.now().date().isoformat(),  # For setting max date in template
    }

    return render(request, "user/property_sale_detail.html", context)


@login_required
@admin_required
def pay_commission(request, commission_id):
    """Mark a single commission as paid"""
    if request.method == "POST" and request.user.is_staff:
        commission = get_object_or_404(Commission, pk=commission_id)
        commission.mark_as_paid()
        messages.success(
            request, f"Commission #{commission_id} has been marked as paid."
        )
        return redirect("realtor_detail", id=commission.realtor.id)
    return redirect("home")


# =============================================================================


@login_required
@admin_required
def frontend_extras(request):
    """Main view for Frontend Extras dashboard"""
    return render(request, "user/frontend_extras.html")

    


@login_required
def property_sale_invoice(request, sale_id):
    """
    View for displaying and printing a property sale invoice
    """
    sale = get_object_or_404(PropertySale, id=sale_id)
    payments = Payment.objects.filter(property_sale=sale).order_by("-payment_date")

    # Calculate balance due
    balance_due = sale.selling_price - sale.amount_paid
    # Get or create general settings (singleton pattern - only one instance)
    # Don't force id=1 to avoid conflicts with database sequences
    settings, created = General.objects.get_or_create()
    # If multiple exist, use the first one
    if not created and General.objects.count() > 1:
        settings = General.objects.first()

    context = {
        "sale": sale,
        "payments": payments,
        "balance_due": balance_due,
        "now": timezone.now(),
        # 'settings':General.objects.all()
        "settings": settings,
        # **company_info,
    }

    return render(request, "user/property_sale_invoice.html", context)


@login_required
@admin_required
def commissions_list(request):
    """View to display all commissions with search and filtering"""
    # Initialize query
    commissions = Commission.objects.all().order_by("-created_at")

    # Search parameters
    search_query = request.GET.get("search", "")
    payment_status = request.GET.get("payment_status", "")
    realtor_id = request.GET.get("realtor_id", "")
    property_ref = request.GET.get("property_ref", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    # In your view function
    realtor_status = request.GET.get("realtor_status", "")

    # Apply the filter if realtor_status is provided

    # Apply filters
    if search_query:
        # Search by reference number, property reference, or realtor name
        commissions = commissions.filter(
            Q(property_reference__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(realtor__first_name__icontains=search_query)
            | Q(realtor__last_name__icontains=search_query)
        )

    if payment_status:
        is_paid = payment_status == "paid"
        commissions = commissions.filter(is_paid=is_paid)

    if realtor_id:
        commissions = commissions.filter(realtor_id=realtor_id)

    if property_ref:
        commissions = commissions.filter(property_reference__icontains=property_ref)

    if date_from:
        commissions = commissions.filter(created_at__gte=date_from)

    if date_to:
        commissions = commissions.filter(created_at__lte=date_to)

    if realtor_status:
        commissions = commissions.filter(realtor__status=realtor_status)

    # Calculate summary statistics
    total_commissions = commissions.aggregate(Sum("amount"))["amount__sum"] or 0
    paid_commissions = (
        commissions.filter(is_paid=True).aggregate(Sum("amount"))["amount__sum"] or 0
    )
    unpaid_commissions = (
        commissions.filter(is_paid=False).aggregate(Sum("amount"))["amount__sum"] or 0
    )

    # Get all realtors for the filter dropdown
    realtors = Realtor.objects.all().order_by("first_name", "last_name")

    # Pagination
    paginator = Paginator(commissions, 20)  # Show 20 commissions per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "total_commissions": total_commissions,
        "paid_commissions": paid_commissions,
        "unpaid_commissions": unpaid_commissions,
        "realtors": realtors,
        "search_query": search_query,
        "payment_status": payment_status,
        "property_ref": property_ref,
        "realtor_id": int(realtor_id) if realtor_id and realtor_id.isdigit() else None,
        "date_from": date_from,
        "date_to": date_to,
        # Pass it to the template context
        "realtor_status": realtor_status,
    }

    return render(request, "user/commissions_list.html", context)


@login_required
@admin_required
def unpaid_commissions_print(request):
    """View to display unpaid commissions in a printable format"""
    # Get all unpaid commissions with related data
    unpaid_commissions = (
        Commission.objects.filter(is_paid=False)
        .select_related("realtor")
        .order_by("realtor__last_name", "realtor__first_name", "-created_at")
    )

    # Get property sales data for property names
    property_sales = {}
    for commission in unpaid_commissions:
        if commission.property_reference:
            try:
                sale = PropertySale.objects.select_related("property_item").get(
                    reference_number=commission.property_reference
                )
                property_sales[commission.property_reference] = sale
            except PropertySale.DoesNotExist:
                property_sales[commission.property_reference] = None

    from django.db import models

    # Calculate totals
    total_unpaid_amount = (
        unpaid_commissions.aggregate(total=models.Sum("amount"))["total"] or 0
    )

    # Group commissions by realtor for better organization
    commissions_by_realtor = {}
    for commission in unpaid_commissions:
        realtor_id = commission.realtor.id
        if realtor_id not in commissions_by_realtor:
            commissions_by_realtor[realtor_id] = {
                "realtor": commission.realtor,
                "commissions": [],
                "total": 0,
            }
        commissions_by_realtor[realtor_id]["commissions"].append(commission)
        commissions_by_realtor[realtor_id]["total"] += commission.amount

    context = {
        "unpaid_commissions": unpaid_commissions,
        "commissions_by_realtor": commissions_by_realtor,
        "property_sales": property_sales,
        "total_unpaid_amount": total_unpaid_amount,
        "total_realtors": len(commissions_by_realtor),
        "total_commissions_count": unpaid_commissions.count(),
        "print_date": timezone.now(),
    }

    return render(request, "user/unpaid_commissions_print.html", context)


@login_required
@admin_required
def realtor_unpaid_commissions_print(request, realtor_id):
    """View to display unpaid commissions for a specific realtor in a printable format"""
    # Get the specific realtor
    realtor = get_object_or_404(Realtor, id=realtor_id)

    # Get unpaid commissions for this specific realtor
    unpaid_commissions = Commission.objects.filter(
        realtor=realtor, is_paid=False
    ).order_by("-created_at")

    # Get property sales data for property names
    property_sales = {}
    for commission in unpaid_commissions:
        if commission.property_reference:
            try:
                sale = PropertySale.objects.select_related("property_item").get(
                    reference_number=commission.property_reference
                )
                property_sales[commission.property_reference] = sale
            except PropertySale.DoesNotExist:
                property_sales[commission.property_reference] = None

    from django.db import models

    # Calculate total unpaid amount for this realtor
    total_unpaid_amount = (
        unpaid_commissions.aggregate(total=models.Sum("amount"))["total"] or 0
    )

    context = {
        "realtor": realtor,
        "unpaid_commissions": unpaid_commissions,
        "property_sales": property_sales,
        "total_unpaid_amount": total_unpaid_amount,
        "print_date": timezone.now(),
    }

    return render(request, "user/realtor_unpaid_commissions_print.html", context)


# =============================================================================================
# ==================================Password reset===============================
def password_reset_request(request):
    """
    View for handling password reset requests
    """
    if request.method == "POST":
        password_reset_form = PasswordResetForm(request.POST)
        if password_reset_form.is_valid():
            data = password_reset_form.cleaned_data["email"]
            associated_users = User.objects.filter(Q(email=data))
            if associated_users.exists():
                for user in associated_users:
                    subject = "Password Reset Requested"
                    email_template_name = "user/password_reset_email.txt"
                    c = {
                        "email": user.email,
                        "domain": request.META["HTTP_HOST"],
                        "site_name": "Triple D Big Dream Homes",
                        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                        "user": user,
                        "token": default_token_generator.make_token(user),
                        "protocol": "https" if request.is_secure() else "http",
                    }
                    email = render_to_string(email_template_name, c)
                    try:
                        send_mail(
                            subject,
                            email,
                            "info@tripledhomes.com.ng",
                            [user.email],
                            fail_silently=False,
                        )
                    except BadHeaderError:
                        return HttpResponse("Invalid header found.")
                    return redirect("password_reset_done")
            else:
                messages.error(request, "No account found with that email address.")
                return redirect("password_reset")
    else:
        password_reset_form = PasswordResetForm()

    return render(
        request,
        "user/password_reset.html",
        {"password_reset_form": password_reset_form},
    )


def password_reset_done(request):
    """
    View shown after password reset request is processed
    """
    return render(request, "user/password_reset_done.html")


def password_reset_confirm(request, uidb64, token):
    """
    View for confirming password reset and setting new password
    """
    from django.utils.http import urlsafe_base64_decode

    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == "POST":
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(
                    request,
                    "Your password has been set. You may go ahead and log in now.",
                )
                return redirect("password_reset_complete")
        else:
            form = SetPasswordForm(user)
        return render(request, "user/password_reset_confirm.html", {"form": form})
    else:
        messages.error(
            request,
            "The password reset link was invalid, possibly because it has already been used. Please request a new password reset.",
        )
        return redirect("signin")


def password_reset_complete(request):
    """
    View shown after password has been successfully reset
    """
    return render(request, "user/password_reset_complete.html")


@login_required
@admin_required
def general_settings(request):
    """
    View to handle displaying and updating general settings
    """
    # Get or create general settings object (assuming only one instance exists)
    # Get or create general settings (singleton pattern - only one instance)
    # Don't force id=1 to avoid conflicts with database sequences
    settings, created = General.objects.get_or_create()
    # If multiple exist, use the first one
    if not created and General.objects.count() > 1:
        settings = General.objects.first()

    if request.method == "POST":
        # Update settings with form data
        settings.company_bank_name = request.POST.get("bank_name")
        settings.company_account_name = request.POST.get(
            "account_name"
        )  # Note: there's a typo in your model (ame not name)
        settings.company_account_number = request.POST.get("account_number")

        # Save the settings
        settings.save()

        # Add success message
        messages.success(request, "Settings updated successfully!")

        # Redirect to the same page to prevent form resubmission
        return redirect("general_settings")

    # Prepare context for template rendering
    context = {"settings": settings, "page_title": "General Settings"}

    return render(request, "user/general_settings.html", context)




def custom_404_view(request, exception):
    """
    Custom 404 error handler that renders our 404.html template
    """
    return render(request, "user/404.html", status=404)



# ----------------==================================-----------------------------------

@login_required
@admin_required
@require_http_methods(["POST"])
def toggle_realtor_status(request, realtor_id):
    """
    Toggle realtor status between regular and executive.
    Only staff members can access this view.
    """
    realtor = get_object_or_404(Realtor, id=realtor_id)

    # Store the old status for the success message
    old_status = realtor.status_display

    # Toggle status
    if realtor.status == "regular":
        realtor.promote_to_executive()
        new_status = "Executive"
        message = f"{realtor.full_name} has been promoted to Executive Realtor! 👑"
        message_tag = "success"
    else:
        realtor.demote_to_regular()
        new_status = "Regular"
        message = f"{realtor.full_name} has been changed to Regular Realtor."
        message_tag = "info"

    # Add success message
    messages.add_message(
        request,
        messages.SUCCESS if message_tag == "success" else messages.INFO,
        message,
    )

    # If it's an AJAX request, return JSON
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "success": True,
                "new_status": new_status,
                "is_executive": realtor.is_executive,
                "message": message,
            }
        )

    # Redirect back to the realtor detail page
    return redirect("realtor_detail", id=realtor.id)


@login_required
@admin_required
@require_http_methods(["POST"])
def bulk_update_realtor_status(request):
    """
    Bulk update multiple realtors' status.
    Expects POST data with realtor_ids and target_status.
    """
    realtor_ids = request.POST.getlist("realtor_ids")
    target_status = request.POST.get("target_status")

    if not realtor_ids or target_status not in ["regular", "executive"]:
        messages.error(request, "Invalid request parameters.")
        return redirect("realtor_list")  # Adjust to your realtor list URL

    realtors = Realtor.objects.filter(id__in=realtor_ids)
    updated_count = 0

    for realtor in realtors:
        if target_status == "executive" and realtor.status == "regular":
            realtor.promote_to_executive()
            updated_count += 1
        elif target_status == "regular" and realtor.status == "executive":
            realtor.demote_to_regular()
            updated_count += 1

    if updated_count > 0:
        status_name = "Executive" if target_status == "executive" else "Regular"
        messages.success(
            request,
            f"{updated_count} realtor(s) have been updated to {status_name} status.",
        )
    else:
        messages.info(request, "No realtors were updated.")

    return redirect("realtor_list")  # Adjust to your realtor list URL


# Optional: API endpoint for AJAX status updates
def realtor_status_api(request, realtor_id):
    """
    API endpoint for realtor status operations.
    GET: Return current status
    POST: Update status
    """
    realtor = get_object_or_404(Realtor, id=realtor_id)

    if request.method == "GET":
        return JsonResponse(
            {
                "realtor_id": realtor.id,
                "full_name": realtor.full_name,
                "status": realtor.status,
                "status_display": realtor.status_display,
                "is_executive": realtor.is_executive,
            }
        )

    elif request.method == "POST":
        new_status = request.POST.get("status")

        if new_status not in ["regular", "executive"]:
            return JsonResponse({"error": "Invalid status"}, status=400)

        if new_status != realtor.status:
            old_status = realtor.status_display

            if new_status == "executive":
                realtor.promote_to_executive()
                message = f"{realtor.full_name} promoted to Executive! 👑"
            else:
                realtor.demote_to_regular()
                message = f"{realtor.full_name} changed to Regular Realtor."

            return JsonResponse(
                {
                    "success": True,
                    "old_status": old_status,
                    "new_status": realtor.status_display,
                    "is_executive": realtor.is_executive,
                    "message": message,
                }
            )

        return JsonResponse(
            {
                "success": True,
                "message": "No change needed - realtor already has this status.",
            }
        )


# /=====================================================

def realtor_register(request, referral_code=None):
    # Determine sponsor code
    sponsor_code = (
        referral_code if referral_code else "29496781"
    )  # Default sponsor code

    # Verify if referral code exists (optional validation)
    sponsor_exists = False
    if referral_code:
        sponsor_exists = Realtor.objects.filter(referral_code=referral_code).exists()
        if not sponsor_exists:
            sponsor_code = "29496781"  # Fall back to default if invalid

    if request.method == "POST":
        try:
            # Get form data
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip()
            phone = request.POST.get("phone", "").strip()
            address = request.POST.get("address", "").strip()
            country = request.POST.get("country", "").strip()
            bank_name = request.POST.get("bank_name", "").strip()
            account_number = request.POST.get("account_number", "").strip()
            account_name = request.POST.get("account_name", "").strip()
            sponsor_code_form = request.POST.get("sponsor_code", "").strip()

            # Basic validation
            if not all(
                [
                    first_name,
                    last_name,
                    email,
                    phone,
                    address,
                    country,
                    bank_name,
                    account_number,
                    account_name,
                ]
            ):
                messages.error(request, "All fields are required.")
                return render(
                    request,
                    "realtor_register.html",
                    {"sponsor_code": sponsor_code, "form_data": request.POST},
                )

            # Validate Nigerian phone number
            import re
            nigerian_phone_pattern = r'^(\+?234|0)[7-9][0-1]\d{8}$'
            if not re.match(nigerian_phone_pattern, phone.replace(' ', '').replace('-', '')):
                messages.error(
                    request, 
                    "Please enter a valid Nigerian phone number (e.g., +2348012345678, 08012345678, or 2348012345678)"
                )
                return render(
                    request,
                    "realtor_register.html",
                    {"sponsor_code": sponsor_code, "form_data": request.POST},
                )
            
            # Validate country is Nigeria
            if country.lower() != 'nigeria':
                messages.error(request, "Registration is currently only available for Nigerian realtors.")
                return render(
                    request,
                    "realtor_register.html",
                    {"sponsor_code": sponsor_code, "form_data": request.POST},
                )
            
            # Check if email already exists
            if Realtor.objects.filter(email=email).exists():
                messages.error(request, "A realtor with this email already exists.")
                return render(
                    request,
                    "realtor_register.html",
                    {"sponsor_code": sponsor_code, "form_data": request.POST},
                )

            # Handle image upload
            image = request.FILES.get("image")

            # Create new realtor
            realtor = Realtor(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                address=address,
                country=country,
                bank_name=bank_name,
                account_number=account_number,
                account_name=account_name,
                sponsor_code=sponsor_code_form,
                image=image,
            )

            realtor.save()  # This will trigger the save method and generate referral_code

            # Send welcome email immediately after successful registration
            try:
                # Construct referral link
                referral_link = f"{request.build_absolute_uri('/').rstrip('/')}/realtor/register/{realtor.referral_code}/"

                # Email subject
                subject = "Welcome to Triple D Big Dream Homes - Your Registration is Complete!"

                # Email message
                message = f"""
Dear {first_name} {last_name},

🎉 Welcome to Triple D Big Dream Homes! 🎉

Congratulations! Your registration as a Professional Realtor has been successfully completed.

Here are your important details:

📋 ACCOUNT INFORMATION:
• Name: {first_name} {last_name}
• Email: {email}
• Phone: {phone}
• Country: {country}

🔗 YOUR REFERRAL DETAILS:
• Your Referral Code: {realtor.referral_code}
• Your Referral Link: {referral_link}

💡 HOW TO USE YOUR REFERRAL:
Share your referral link with potential realtors to earn commissions when they register and make sales. Your unique referral code ({realtor.referral_code}) will automatically be applied when someone uses your link.

🚀 NEXT STEPS:
1. Save your referral code and link in a safe place
2. Start sharing your referral link to grow your network
3. Contact our support team if you have any questions

Thank you for joining Triple D Big Dream Homes. We're excited to have you as part of our professional realtor community!

Best regards,
The Triple D Big Dream Homes Team

---
This is an automated message. Please do not reply to this email.
For support, contact us through our official channels.
                """.strip()

                # Send the email
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )

                logger.info(f"Welcome email sent successfully to {email}")
                messages.success(
                    request,
                    "Registration successful! A welcome email with your referral details has been sent to your email address.",
                )

            except Exception as email_error:
                logger.error(
                    f"Failed to send welcome email to {email}: {str(email_error)}"
                )
                messages.warning(
                    request,
                    "Registration successful! However, there was an issue sending the welcome email. Please contact support for your referral details.",
                )

            # Redirect to success page or show success message with referral code
            return render(
                request,
                "estate/realtor_register_success.html",
                {"realtor": realtor, "referral_code": realtor.referral_code},
            )

        except Exception as e:
            logger.error(f"Registration failed for {email}: {str(e)}")
            messages.error(request, f"Registration failed: {str(e)}")
            return render(
                request,
                "estate/realtor_register.html",
                {"sponsor_code": sponsor_code, "form_data": request.POST},
            )

    # GET request - show form
    return render(
        request,
        "estate/realtor_register.html",
        {"sponsor_code": sponsor_code, "referral_code": referral_code},
    )


"""nice work here"""


# ========================SECRETARY ADMIN VIEWS=================================


@login_required
@admin_required
def secretary_list(request):
    """List all secretary admins"""
    secretaries = SecretaryAdmin.objects.all().order_by("-created_at")
    return render(request, "user/secretary_list.html", {"secretaries": secretaries})


@login_required
@admin_required
def create_secretary(request):
    """Create a new secretary admin"""
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone_number = request.POST.get("phone_number")
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Validate required fields
        if not all([full_name, email, username, password]):
            messages.error(request, "All required fields must be filled.")
            return render(request, "user/create_secretary.html")

        # Check if username or email already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, "user/create_secretary.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return render(request, "user/create_secretary.html")

        try:
            with transaction.atomic():
                # Create user account
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=full_name.split()[0],
                    last_name=" ".join(full_name.split()[1:])
                    if len(full_name.split()) > 1
                    else "",
                )
                
                # CRITICAL: Verify user got an ID
                if not user.pk:
                    raise ValueError("User was created but did not receive an ID. This should never happen.")

                # Create secretary admin profile
                secretary = SecretaryAdmin.objects.create(
                    user=user,
                    full_name=full_name,
                    email=email,
                    phone_number=phone_number,
                    created_by=request.user,
                )
                
                # CRITICAL: Verify secretary got an ID
                if not secretary.pk:
                    raise ValueError("SecretaryAdmin was created but did not receive an ID. This should never happen.")

                messages.success(
                    request, f'Secretary admin "{full_name}" created successfully!'
                )
                return redirect("secretary_list")

        except Exception as e:
            messages.error(request, f"Error creating secretary admin: {str(e)}")

    return render(request, "user/create_secretary.html")


@login_required
@admin_required
def edit_secretary(request, secretary_id):
    """Edit secretary admin details"""
    secretary = get_object_or_404(SecretaryAdmin, id=secretary_id)

    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone_number = request.POST.get("phone_number")
        username = request.POST.get("username")
        is_active = request.POST.get("is_active") == "on"

        # Validate required fields
        if not all([full_name, email, username]):
            messages.error(request, "All required fields must be filled.")
            return render(request, "user/edit_secretary.html", {"secretary": secretary})

        # Check if username or email already exists (excluding current user)
        if (
            User.objects.filter(username=username)
            .exclude(id=secretary.user.id)
            .exists()
        ):
            messages.error(request, "Username already exists.")
            return render(request, "user/edit_secretary.html", {"secretary": secretary})

        if User.objects.filter(email=email).exclude(id=secretary.user.id).exists():
            messages.error(request, "Email already exists.")
            return render(request, "user/edit_secretary.html", {"secretary": secretary})

        try:
            with transaction.atomic():
                # Update user account
                secretary.user.username = username
                secretary.user.email = email
                secretary.user.first_name = full_name.split()[0]
                secretary.user.last_name = (
                    " ".join(full_name.split()[1:])
                    if len(full_name.split()) > 1
                    else ""
                )
                secretary.user.is_active = is_active
                secretary.user.save()

                # Update secretary profile
                secretary.full_name = full_name
                secretary.email = email
                secretary.phone_number = phone_number
                secretary.is_active = is_active
                secretary.save()

                messages.success(
                    request, f'Secretary admin "{full_name}" updated successfully!'
                )
                return redirect("secretary_list")

        except Exception as e:
            messages.error(request, f"Error updating secretary admin: {str(e)}")

    return render(request, "user/edit_secretary.html", {"secretary": secretary})


@login_required
@admin_required
def delete_secretary(request, secretary_id):
    """Delete secretary admin"""
    secretary = get_object_or_404(SecretaryAdmin, id=secretary_id)

    if request.method == "POST":
        try:
            with transaction.atomic():
                secretary_name = secretary.full_name
                secretary.user.delete()  # This will also delete the secretary profile
                messages.success(
                    request, f'Secretary admin "{secretary_name}" deleted successfully!'
                )
        except Exception as e:
            messages.error(request, f"Error deleting secretary admin: {str(e)}")

    return redirect("secretary_list")


@login_required
@admin_required
def toggle_secretary_status(request, secretary_id):
    """Toggle secretary admin active status"""
    secretary = get_object_or_404(SecretaryAdmin, id=secretary_id)

    try:
        secretary.is_active = not secretary.is_active
        secretary.user.is_active = secretary.is_active
        secretary.save()
        secretary.user.save()

        status = "activated" if secretary.is_active else "deactivated"
        messages.success(
            request, f'Secretary admin "{secretary.full_name}" {status} successfully!'
        )
    except Exception as e:
        messages.error(request, f"Error updating secretary status: {str(e)}")

    return redirect("secretary_list")


def generate_random_password(length=8):
    """Generate a random password"""
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


@login_required
@admin_required
def reset_secretary_password(request, secretary_id):
    """Reset secretary admin password"""
    secretary = get_object_or_404(SecretaryAdmin, id=secretary_id)

    if request.method == "POST":
        new_password = request.POST.get("new_password")

        if not new_password:
            messages.error(request, "New password is required.")
            return redirect("secretary_list")

        try:
            secretary.user.set_password(new_password)
            secretary.user.save()
            messages.success(
                request, f'Password reset for "{secretary.full_name}" successfully!'
            )
        except Exception as e:
            messages.error(request, f"Error resetting password: {str(e)}")

    return redirect("secretary_list")


# ========================CHIEF ACCOUNTANT VIEWS=================================


@login_required
@admin_required
def chief_accountant_list(request):
    """List all chief accountants"""
    chief_accountants = User.objects.filter(user_type='chief_accountant').order_by("-date_joined")
    return render(request, "user/chief_accountant_list.html", {"chief_accountants": chief_accountants})


@login_required
@admin_required
def create_chief_accountant(request):
    """Create a new chief accountant"""
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone_number = request.POST.get("phone_number")
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Validate required fields
        if not all([full_name, email, username, password]):
            messages.error(request, "All required fields must be filled.")
            return render(request, "user/create_chief_accountant.html")

        # Check if username or email already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, "user/create_chief_accountant.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return render(request, "user/create_chief_accountant.html")

        try:
            with transaction.atomic():
                # Create user account
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=full_name.split()[0],
                    last_name=" ".join(full_name.split()[1:])
                    if len(full_name.split()) > 1
                    else "",
                    user_type='chief_accountant',
                    phone=phone_number
                )

                messages.success(
                    request, f'Chief Accountant "{full_name}" created successfully!'
                )
                return redirect("chief_accountant_list")

        except Exception as e:
            messages.error(request, f"Error creating chief accountant: {str(e)}")

    return render(request, "user/create_chief_accountant.html")


@login_required
@admin_required
def edit_chief_accountant(request, user_id):
    """Edit chief accountant details"""
    try:
        chief_accountant = User.objects.get(id=user_id, user_type='chief_accountant')
    except User.DoesNotExist:
        messages.error(request, "Chief Accountant not found.")
        return redirect("chief_accountant_list")

    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone_number = request.POST.get("phone_number")
        # username cannot be changed easily

        # Validate required fields
        if not all([full_name, email]):
            messages.error(request, "Name and Email are required.")
            return render(
                request,
                "user/edit_chief_accountant.html",
                {"chief_accountant": chief_accountant},
            )

        # Check email uniqueness
        if User.objects.exclude(id=user_id).filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return render(
                request,
                "user/edit_chief_accountant.html",
                {"chief_accountant": chief_accountant},
            )

        try:
            chief_accountant.first_name = full_name.split()[0]
            chief_accountant.last_name = (
                " ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else ""
            )
            chief_accountant.email = email
            chief_accountant.phone = phone_number
            chief_accountant.save()

            messages.success(request, "Chief Accountant details updated successfully.")
            return redirect("chief_accountant_list")
        except Exception as e:
            messages.error(request, f"Error updating details: {str(e)}")

    return render(
        request,
        "user/edit_chief_accountant.html",
        {"chief_accountant": chief_accountant},
    )


@login_required
@admin_required
def delete_chief_accountant(request, user_id):
    """Delete chief accountant"""
    if request.method == "POST":
        try:
            chief_accountant = User.objects.get(id=user_id, user_type='chief_accountant')
            name = chief_accountant.get_full_name()
            chief_accountant.delete()
            messages.success(request, f'Chief Accountant "{name}" deleted successfully.')
        except User.DoesNotExist:
            messages.error(request, "Chief Accountant not found.")
        except Exception as e:
            messages.error(request, f"Error deleting user: {str(e)}")

    return redirect("chief_accountant_list")


@login_required
@admin_required
def toggle_chief_accountant_status(request, user_id):
    """Toggle chief accountant active status"""
    try:
        chief_accountant = User.objects.get(id=user_id, user_type='chief_accountant')
        chief_accountant.is_active = not chief_accountant.is_active
        chief_accountant.save()

        status = "activated" if chief_accountant.is_active else "deactivated"
        messages.success(
            request, f'Chief Accountant "{chief_accountant.get_full_name()}" {status}.'
        )
    except User.DoesNotExist:
        messages.error(request, "Chief Accountant not found.")

    return redirect("chief_accountant_list")


@login_required
@admin_required
def reset_chief_accountant_password(request, user_id):
    """Reset chief accountant password"""
    try:
        chief_accountant = User.objects.get(id=user_id, user_type='chief_accountant')

        if request.method == "POST":
            password = request.POST.get("password")
            if password:
                chief_accountant.set_password(password)
                chief_accountant.save()
                messages.success(
                    request,
                    f'Password for "{chief_accountant.get_full_name()}" reset successfully.',
                )
            else:
                messages.error(request, "Password cannot be empty.")

    except User.DoesNotExist:
        messages.error(request, "Chief Accountant not found.")

    return redirect("chief_accountant_list")


# ===========================SECRETARY DASHBOARD================================

@login_required
def secretary_dashboard(request):
    """
    Secretary dashboard view with limited statistics and recent data
    """
    # Check if user is a secretary (optional additional check)
    if not hasattr(request, "is_secretary") or not request.is_secretary:
        # You can redirect non-secretary users or handle differently
        pass

    # Get realtor statistics
    total_realtors = Realtor.objects.count()
    # Count executive realtors instead of active realtors
    executive_realtors = Realtor.objects.filter(status="executive").count()

    # Get recent realtors (last 5) - ordered by created_at
    recent_realtors = Realtor.objects.order_by("-created_at")[:5]

    # Get sales statistics using correct field names from PropertySale model
    total_sales = PropertySale.objects.count()

    # Use selling_price for total sales value
    total_sales_value = (
        PropertySale.objects.aggregate(total=Sum("selling_price"))["total"] or 0
    )

    # Get recent sales (last 5) with related property data
    recent_sales = PropertySale.objects.select_related("property_item").order_by(
        "-created_at"
    )[:5]

    context = {
        "total_realtors": total_realtors,
        "executive_realtors": executive_realtors,  # Changed from active_realtors
        "recent_realtors": recent_realtors,
        "total_sales": total_sales,
        "total_sales_value": total_sales_value,
        "recent_sales": recent_sales,
    }

    return render(request, "user/secretary_dashboard.html", context)
