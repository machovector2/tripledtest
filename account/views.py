from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.utils import timezone
from decimal import Decimal
from .models import *
from .forms import *


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me', False)

            # Support email login
            if '@' in username:
                try:
                    user_obj = User.objects.get(email=username)
                    username = user_obj.username
                except User.DoesNotExist:
                    pass  # Let authenticate fail naturally

            user = authenticate(request, username=username, password=password)
            if user is not None:
                if not user.is_active:
                    messages.error(request, 'Your account has been deactivated. Please contact the administrator.')
                    return render(request, 'signin.html', {'form': form})

                login(request, user)

                # Handle remember me functionality
                if not remember_me:
                    request.session.set_expiry(0)  # Session expires when browser closes
                else:
                    request.session.set_expiry(1209600)  # 2 weeks
                    
                    

                messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')

                # Redirect to next page if specified
                next_page = request.GET.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid username or password.')
        else:
            # Convert form errors to messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    else:
        form = LoginForm()

    return render(request, 'signin.html', {'form': form})


@never_cache
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def dashboard(request):
    if request.user.user_type in ['admin', 'chief_accountant']:
        # Get main branch (Enugu) or create one if it doesn't exist
        main_branch, created = Branch.objects.get_or_create(
            branch_type='main',
            defaults={
                'name': 'Main Branch',
                'location': 'Enugu',
                'state': 'Enugu State',
                'address': 'Main Office Address',
                'created_by': request.user
            }
        )

        sub_branches = Branch.objects.filter(branch_type='sub', is_active=True).order_by('-created_date')
        all_branches = Branch.objects.filter(is_active=True)

        # Calculate totals
        main_income = main_branch.get_total_income()
        main_expenditure = main_branch.get_total_expenditure()
        main_balance = main_branch.get_balance()
        
        # Calculate available funds for allocation (main branch balance)
        available_for_allocation = main_balance

        # All branches combined
        total_income = Transaction.objects.filter(
            transaction_type='income',
            branch__is_active=True
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

        total_expenditure = Transaction.objects.filter(
            transaction_type='expenditure',
            branch__is_active=True
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

        total_balance = total_income - total_expenditure

        # Total allocated funds
        total_allocated = Branch.objects.filter(
            is_active=True
        ).aggregate(Sum('allocated_funds'))['allocated_funds__sum'] or Decimal('0')

        recent_transactions = Transaction.objects.filter(
            branch__is_active=True
        ).select_related('branch', 'created_by').order_by('-created_date')[:10]

        # Branch statistics
        active_admins = User.objects.filter(
            user_type='branch_admin',
            is_active=True
        ).count()

        context = {
            'main_branch': main_branch,
            'sub_branches': sub_branches,
            'all_branches': all_branches,
            'main_income': main_income,
            'main_expenditure': main_expenditure,
            'main_balance': main_balance,
            'available_for_allocation': available_for_allocation,
            'total_income': total_income,
            'total_expenditure': total_expenditure,
            'total_balance': total_balance,
            'total_allocated': total_allocated,
            'recent_transactions': recent_transactions,
            'branches_count': sub_branches.count(),
            'active_admins': active_admins,
        }

    elif request.user.user_type == 'branch_admin':
        # Get the branch this admin manages
        branch = request.user.managed_branch

        if branch:
            branch_income = branch.get_total_income()
            branch_expenditure = branch.get_total_expenditure()
            branch_balance = branch.get_balance()

            recent_transactions = branch.transactions.select_related(
                'income_category', 'expenditure_category', 'created_by'
            ).order_by('-created_date')[:10]

            context = {
                'branch': branch,
                'branch_income': branch_income,
                'branch_expenditure': branch_expenditure,
                'branch_balance': branch_balance,
                'recent_transactions': recent_transactions,
            }
        else:
            messages.error(request, 'No branch assigned to your account. Please contact the administrator.')
            context = {
                'error_message': 'No branch assigned to your account. Please contact the administrator.',
                'show_contact_info': True,
            }
    else:
        # Handle users without proper user_type
        messages.warning(request, 'Your account needs to be configured. Please contact the administrator.')
        context = {
            'info_message': 'Your account is being set up. Please contact the administrator.',
            'show_contact_info': True,
        }

    return render(request, 'home.html', context)


@login_required
def create_branch(request):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can create branches.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = BranchForm(request.POST)

        if form.is_valid():
            branch = form.save(commit=False)
            branch.created_by = request.user
            try:
                branch.save()
                messages.success(request, f'Branch "{branch.name}" created successfully!')
                return redirect('manage_branches')
            except Exception as e:
                messages.error(request, f'Error creating branch: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BranchForm()

    return render(request, 'create_branch.html', {'form': form})


@login_required
def create_branch_admin(request):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can create branch admins.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = BranchAdminForm(request.POST)

        if form.is_valid():
            admin_user = form.save()
            messages.success(request, f'Branch admin "{admin_user.get_full_name()}" created successfully!')
            return redirect('manage_users')
    else:
        form = BranchAdminForm()

    return render(request, 'create_branch_admin.html', {'form': form})


@login_required
def manage_users(request):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can manage users.')
        return redirect('dashboard')

    from django.db.models import Count

    users = User.objects.filter(user_type='branch_admin') \
        .prefetch_related('managed_branches') \
        .annotate(branch_count=Count('managed_branches', distinct=True)) \
        .order_by('-date_joined')

    total_admins = users.count()
    active_admins = users.filter(is_active=True).count()
    inactive_admins = total_admins - active_admins
    unassigned_admins = users.filter(managed_branches__isnull=True).distinct().count()
    total_assigned_branches = Branch.objects.filter(admins__user_type='branch_admin').distinct().count()

    branches = Branch.objects.filter(is_active=True).order_by('name')

    context = {
        'users': users,
        'total_admins': total_admins,
        'active_admins': active_admins,
        'inactive_admins': inactive_admins,
        'unassigned_admins': unassigned_admins,
        'total_assigned_branches': total_assigned_branches,
        'branches': branches,
    }

    return render(request, 'manage_users.html', context)


@login_required
def manage_branches(request):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can manage branches.')
        return redirect('dashboard')

    from django.db.models import Count, Sum
    
    branches = Branch.objects.all() \
        .select_related('created_by') \
        .prefetch_related('admins') \
        .annotate(admin_count=Count('admins', distinct=True)) \
        .order_by('-created_date')
    
    # Calculate statistics
    total_branches = branches.count()
    active_branches = branches.filter(is_active=True).count()
    inactive_branches = total_branches - active_branches
    main_branches = branches.filter(branch_type='main').count()
    sub_branches = branches.filter(branch_type='sub').count()
    
    # Financial statistics
    total_allocated = Branch.objects.filter(is_active=True).aggregate(
        total=Sum('allocated_funds')
    )['total'] or Decimal('0')
    
    # Total balance across all branches
    total_balance = Decimal('0')
    for branch in branches.filter(is_active=True):
        total_balance += branch.get_balance()
    
    context = {
        'branches': branches,
        'total_branches': total_branches,
        'active_branches': active_branches,
        'inactive_branches': inactive_branches,
        'main_branches': main_branches,
        'sub_branches': sub_branches,
        'total_allocated': total_allocated,
        'total_balance': total_balance,
    }
    
    return render(request, 'manage_branches.html', context)


@login_required
def assign_branch_admin(request, branch_id=None, user_id=None):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can assign branch admins.')
        return redirect('dashboard')

    # Get pre-selected branch or user if provided
    pre_selected_branch = None
    pre_selected_user = None
    
    if branch_id:
        try:
            pre_selected_branch = Branch.objects.get(id=branch_id, is_active=True)
        except Branch.DoesNotExist:
            messages.error(request, 'Branch not found.')
            return redirect('manage_branches')
    
    if user_id:
        try:
            pre_selected_user = User.objects.get(id=user_id, user_type='branch_admin')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('manage_users')

    if request.method == 'POST':
        # Handle different cases: branch assignment or user assignment
        if user_id:
            # User is pre-selected, get branches from POST
            selected_branches = request.POST.getlist('branches')
            
            # Clear all existing branch assignments for this user
            pre_selected_user.managed_branches.clear()
            
            # Add new assignments
            if selected_branches:
                branches_assigned = []
                for branch_id_str in selected_branches:
                    try:
                        branch = Branch.objects.get(id=branch_id_str, is_active=True)
                        branch.admins.add(pre_selected_user)
                        branches_assigned.append(branch.name)
                    except Branch.DoesNotExist:
                        pass
                
                if branches_assigned:
                    branch_names = ', '.join(branches_assigned)
                    messages.success(request, f'User "{pre_selected_user.get_full_name()}" assigned to branches: {branch_names}')
                else:
                    messages.warning(request, 'No valid branches selected.')
            else:
                messages.success(request, f'All branch assignments removed from user "{pre_selected_user.get_full_name()}".')
            
            return redirect('manage_users')
        else:
            # Branch case: standard flow
            post_data = request.POST.copy()
            
            # If branch_id is provided but not in POST, add it
            if branch_id and not post_data.get('branch'):
                post_data['branch'] = branch_id
            
            form = BranchAdminAssignmentForm(post_data)

            if form.is_valid():
                branch = form.cleaned_data['branch']
                admins = form.cleaned_data['admins']

                # Clear existing assignments for this branch
                branch.admins.clear()

                # Add new assignments
                if admins:
                    for admin in admins:
                        branch.admins.add(admin)
                    admin_names = ', '.join([admin.get_full_name() for admin in admins])
                    messages.success(request, f'Admins ({admin_names}) assigned to "{branch.name}" successfully!')
                else:
                    messages.success(request, f'All admin assignments removed from "{branch.name}".')
                
                # Redirect based on where user came from
                if branch_id:
                    return redirect('manage_branches')
                else:
                    return redirect('manage_branches')
            else:
                # Display form errors
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
    else:
        # Pre-populate form if branch or user is specified
        initial_data = {}
        if pre_selected_branch:
            initial_data['branch'] = pre_selected_branch
            # Pre-select existing admins for this branch
            initial_data['admins'] = pre_selected_branch.admins.all()
        
        if pre_selected_user:
            # Pre-select branches this user is assigned to
            initial_data['admins'] = [pre_selected_user]
        
        form = BranchAdminAssignmentForm(initial=initial_data)

    # Get all branch admins for template display
    branch_admins = User.objects.filter(user_type='branch_admin').order_by('first_name', 'last_name')
    
    # Get list of currently assigned admin IDs for pre-checking
    assigned_admin_ids = []
    assigned_branch_ids = []
    all_branches = Branch.objects.filter(is_active=True).order_by('name')
    
    if pre_selected_branch:
        assigned_admin_ids = list(pre_selected_branch.admins.values_list('id', flat=True))
    elif pre_selected_user:
        assigned_admin_ids = [pre_selected_user.id]
        # Get branches this user is currently assigned to
        assigned_branch_ids = list(pre_selected_user.managed_branches.values_list('id', flat=True))
    
    context = {
        'form': form,
        'pre_selected_branch': pre_selected_branch,
        'pre_selected_user': pre_selected_user,
        'branch_admins': branch_admins,
        'assigned_admin_ids': assigned_admin_ids,
        'all_branches': all_branches,
        'assigned_branch_ids': assigned_branch_ids,
    }
    
    return render(request, 'assign_branch_admin.html', context)


@login_required
def allocate_funds(request, branch_id=None):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can allocate funds.')
        return redirect('dashboard')

    # Get main branch
    main_branch = Branch.objects.filter(branch_type='main').first()
    if not main_branch:
        messages.error(request, 'Main branch not found. Please create a main branch first.')
        return redirect('manage_branches')
    
    # Get pre-selected branch if provided
    pre_selected_branch = None
    if branch_id:
        try:
            pre_selected_branch = Branch.objects.get(id=branch_id, branch_type='sub', is_active=True)
        except Branch.DoesNotExist:
            messages.error(request, 'Branch not found or is not a sub branch.')
            return redirect('manage_branches')

    if request.method == 'POST':
        form = FundAllocationForm(request.POST, user=request.user)

        if form.is_valid():
            fund_allocation = form.save(commit=False)
            fund_allocation.from_branch = main_branch
            fund_allocation.allocated_by = request.user

            # Update branch allocated funds
            to_branch = fund_allocation.to_branch
            to_branch.allocated_funds += fund_allocation.amount
            to_branch.save()

            fund_allocation.save()

            # Get or create default categories for fund allocation
            income_category, created = IncomeCategory.objects.get_or_create(
                name='Fund Allocation',
                defaults={
                    'description': 'Funds allocated from main branch',
                    'scope': 'all',
                    'created_by': request.user
                }
            )

            expenditure_category, created = ExpenditureCategory.objects.get_or_create(
                name='Fund Allocation',
                defaults={
                    'description': 'Funds allocated to sub branches',
                    'scope': 'all',
                    'created_by': request.user
                }
            )

            # Create income transaction for receiving branch
            Transaction.objects.create(
                branch=to_branch,
                transaction_type='income',
                amount=fund_allocation.amount,
                description=f'Fund allocation received from {main_branch.name}: {fund_allocation.description}',
                date=fund_allocation.allocated_date.date(),
                income_category=income_category,
                fund_allocation=fund_allocation,
                created_by=request.user
            )

            # Create expenditure transaction for main branch (deduction)
            Transaction.objects.create(
                branch=main_branch,
                transaction_type='expenditure',
                amount=fund_allocation.amount,
                description=f'Fund allocation to {to_branch.name}: {fund_allocation.description}',
                date=fund_allocation.allocated_date.date(),
                expenditure_category=expenditure_category,
                fund_allocation=fund_allocation,
                created_by=request.user
            )

            messages.success(request, f'₦{fund_allocation.amount:,.2f} allocated to "{to_branch.name}" successfully!')
            
            # Redirect based on where user came from
            if branch_id:
                return redirect('manage_branches')
            else:
                return redirect('fund_allocations')
        else:
            # Display form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        # Pre-populate form if branch is specified
        initial_data = {}
        if pre_selected_branch:
            initial_data['to_branch'] = pre_selected_branch
        
        form = FundAllocationForm(user=request.user, initial=initial_data)

    # Get available balance from main branch
    main_balance = main_branch.get_balance()
    
    context = {
        'form': form,
        'main_branch': main_branch,
        'main_balance': main_balance,
        'pre_selected_branch': pre_selected_branch,
    }
    
    return render(request, 'allocate_funds.html', context)


@login_required
def fund_allocations(request):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can view fund allocations.')
        return redirect('dashboard')

    allocations = FundAllocation.objects.select_related(
        'from_branch', 'to_branch', 'allocated_by'
    ).order_by('-allocated_date')
    return render(request, 'fund_allocations.html', {'allocations': allocations})


@login_required
def reverse_fund_allocation(request, allocation_id):
    """
    Reverse a fund allocation by creating offsetting transactions.
    This maintains complete audit trail while correcting allocation errors.
    
    IMPORTANT: This does NOT delete the original allocation.
    Instead, it creates a reversal allocation that cancels it out.
    """
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can reverse fund allocations.')
        return redirect('dashboard')
    
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('fund_allocations')
    
    try:
        # Get the original allocation
        original_allocation = FundAllocation.objects.select_related(
            'from_branch', 'to_branch'
        ).get(id=allocation_id)
        
        # Check if already reversed
        if not original_allocation.is_active:
            messages.warning(request, 'This allocation has already been reversed.')
            return redirect('fund_allocations')
        
        # Get branches
        main_branch = original_allocation.from_branch
        sub_branch = original_allocation.to_branch
        amount = original_allocation.amount
        
        # VALIDATE: Check if sub-branch has sufficient balance to reverse
        sub_branch_balance = sub_branch.get_balance()
        if sub_branch_balance < amount:
            messages.error(request,
                f"❌ Cannot Reverse Allocation!\n\n"
                f"The allocation of ₦{amount:,.2f} cannot be reversed because {sub_branch.name} "
                f"only has ₦{sub_branch_balance:,.2f} available.\n\n"
                f"The branch has already spent ₦{(amount - sub_branch_balance):,.2f} of the allocated funds.\n\n"
                f"Please ensure {sub_branch.name} has sufficient balance before reversing this allocation."
            )
            return redirect('fund_allocations')
        
        # Create the reversal allocation record
        reversal_allocation = FundAllocation.objects.create(
            from_branch=sub_branch,  # Reversed: now from sub to main
            to_branch=main_branch,   # Reversed: now to main
            amount=amount,
            description=f"REVERSAL of allocation #{original_allocation.id}: {original_allocation.description}",
            allocated_by=request.user,
            is_active=True
        )
        
        # Get or create reversal categories
        income_category, _ = IncomeCategory.objects.get_or_create(
            name='Fund Allocation Reversal',
            defaults={
                'description': 'Reversal of fund allocations',
                'scope': 'all',
                'created_by': request.user
            }
        )
        
        expenditure_category, _ = ExpenditureCategory.objects.get_or_create(
            name='Fund Allocation Reversal',
            defaults={
                'description': 'Reversal of fund allocations',
                'scope': 'all',
                'created_by': request.user
            }
        )
        
        # Create EXPENDITURE transaction for sub-branch (money leaving)
        Transaction.objects.create(
            branch=sub_branch,
            transaction_type='expenditure',
            amount=amount,
            description=f"REVERSAL: Returning ₦{amount:,.2f} to {main_branch.name} (Original allocation #{original_allocation.id})",
            date=timezone.now().date(),
            expenditure_category=expenditure_category,
            fund_allocation=reversal_allocation,
            created_by=request.user
        )
        
        # Create INCOME transaction for main branch (money returning)
        Transaction.objects.create(
            branch=main_branch,
            transaction_type='income',
            amount=amount,
            description=f"REVERSAL: Funds returned from {sub_branch.name} (Original allocation #{original_allocation.id})",
            date=timezone.now().date(),
            income_category=income_category,
            fund_allocation=reversal_allocation,
            created_by=request.user
        )
        
        # Update allocated funds on sub-branch
        sub_branch.allocated_funds -= amount
        sub_branch.save()
        
        # Mark original allocation as inactive (reversed)
        original_allocation.is_active = False
        original_allocation.save()
        
        messages.success(request, 
            f"✅ Fund Allocation Reversed Successfully!\n\n"
            f"₦{amount:,.2f} has been returned from {sub_branch.name} to {main_branch.name}.\n\n"
            f"Both the original allocation and the reversal are preserved in the audit trail."
        )
        
    except FundAllocation.DoesNotExist:
        messages.error(request, 'Allocation not found.')
    except Exception as e:
        messages.error(request, f'Error reversing allocation: {str(e)}')
    
    return redirect('fund_allocations')


@login_required
def delete_fund_allocation(request, allocation_id):
    """
    Block deletion of fund allocations for audit compliance.
    Redirects to fund allocations with error message.
    """
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can manage fund allocations.')
        return redirect('dashboard')
    
    messages.error(request, 
        "❌ Fund Allocations Cannot Be Deleted!\n\n"
        "For financial integrity and audit compliance, fund allocations cannot be deleted.\n\n"
        "To correct an error, please use the 'REVERSE' button instead. "
        "This creates offsetting transactions that maintain a complete audit trail.\n\n"
        "The reversal will:\n"
        "• Return the funds from the sub-branch to the main branch\n"
        "• Create proper accounting entries for both branches\n"
        "• Mark the original allocation as reversed\n"
        "• Preserve complete transaction history"
    )
    return redirect('fund_allocations')


@login_required
def transactions(request):
    if request.user.user_type in ['admin', 'chief_accountant']:
        transactions_list = Transaction.objects.select_related(
            'branch', 'created_by', 'income_category', 'expenditure_category'
        ).filter(branch__is_active=True)
        branches = Branch.objects.filter(is_active=True).order_by('name')
    else:
        branch = request.user.managed_branch
        if not branch:
            messages.error(request, 'No branch assigned to your account.')
            return redirect('dashboard')
        transactions_list = branch.transactions.select_related(
            'created_by', 'income_category', 'expenditure_category'
        )
        branches = None

    # Filter by branch if requested
    branch_filter = request.GET.get('branch')
    if branch_filter and request.user.user_type in ['admin', 'chief_accountant']:
        transactions_list = transactions_list.filter(branch_id=branch_filter)

    # Filter by type
    type_filter = request.GET.get('type')
    if type_filter:
        transactions_list = transactions_list.filter(transaction_type=type_filter)
    
    # Filter by category
    income_category_filter = request.GET.get('income_category')
    expenditure_category_filter = request.GET.get('expenditure_category')
    if income_category_filter:
        transactions_list = transactions_list.filter(income_category_id=income_category_filter)
    if expenditure_category_filter:
        transactions_list = transactions_list.filter(expenditure_category_id=expenditure_category_filter)

    # Date range filter
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        transactions_list = transactions_list.filter(date__gte=start_date)
    if end_date:
        transactions_list = transactions_list.filter(date__lte=end_date)

    # Order by date
    transactions_list = transactions_list.order_by('-date', '-created_date')

    # Calculate totals for the filtered transactions
    total_income = transactions_list.filter(transaction_type='income').aggregate(
        Sum('amount'))['amount__sum'] or Decimal('0')
    total_expenditure = transactions_list.filter(transaction_type='expenditure').aggregate(
        Sum('amount'))['amount__sum'] or Decimal('0')
    net_balance = total_income - total_expenditure

    # Get categories for filter dropdowns
    income_categories = IncomeCategory.objects.filter(is_active=True).order_by('name')
    expenditure_categories = ExpenditureCategory.objects.filter(is_active=True).order_by('name')
    
    context = {
        'transactions': transactions_list[:100],  # Limit to 100 for performance
        'branches': branches,
        'total_income': total_income,
        'total_expenditure': total_expenditure,
        'net_balance': net_balance,
        'selected_branch': branch_filter,
        'selected_type': type_filter,
        'start_date': start_date,
        'end_date': end_date,
        'income_categories': income_categories,
        'expenditure_categories': expenditure_categories,
        'selected_income_category': income_category_filter,
        'selected_expenditure_category': expenditure_category_filter,
    }
    return render(request, 'transactions.html', context)


@login_required
def add_transaction(request):
    # Check if branch admin is trying to add income (not allowed)
    if request.user.user_type == 'branch_admin':
        if request.method == 'POST':
            transaction_type = request.POST.get('transaction_type')
            if transaction_type == 'income':
                messages.error(request, 'Branch administrators can only add expenditure transactions. Income can only be added by the main administrator.')
                return redirect('add_transaction')
    
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.created_by = request.user

            # Set branch based on user type
            if request.user.user_type in ['admin', 'chief_accountant']:
                transaction.branch = form.cleaned_data['branch']
            else:
                branch = request.user.managed_branch
                if not branch:
                    messages.error(request, 'No branch assigned to your account.')
                    return redirect('dashboard')
                transaction.branch = branch

            # Note: Balance validation is already handled in the form's clean method
            transaction.save()
            messages.success(request, 'Transaction added successfully!')
            return redirect('transactions')
        else:
            # Form is invalid - display validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = TransactionForm(user=request.user)

    return render(request, 'add_transaction.html', {'form': form})


@login_required
def add_income(request):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountantistrators can add income transactions.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user, transaction_type='income')
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.created_by = request.user
            transaction.transaction_type = 'income'  # Force income type
            transaction.branch = form.cleaned_data['branch']

            transaction.save()
            messages.success(request, 'Income transaction added successfully!')
            return redirect('transactions')
        else:
            # Form is invalid - display validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = TransactionForm(user=request.user, transaction_type='income')

    return render(request, 'add_transaction.html', {'form': form, 'transaction_type': 'income'})


@login_required
def add_expenditure(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST, user=request.user, transaction_type='expenditure')
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.created_by = request.user
            transaction.transaction_type = 'expenditure'  # Force expenditure type

            # Set branch based on user type
            if request.user.user_type in ['admin', 'chief_accountant']:
                transaction.branch = form.cleaned_data['branch']
            else:
                branch = request.user.managed_branch
                if not branch:
                    messages.error(request, 'No branch assigned to your account.')
                    return redirect('dashboard')
                transaction.branch = branch

            # Note: Balance validation is already handled in the form's clean method
            try:
                transaction.save()
                messages.success(request, 'Expenditure transaction added successfully!')
                return redirect('transactions')
            except Exception as e:
                messages.error(request, f'Error saving transaction: {str(e)}')
                return render(request, 'add_transaction.html', {'form': form, 'transaction_type': 'expenditure'})
        else:
            # Form is invalid - display validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = TransactionForm(user=request.user, transaction_type='expenditure')

    return render(request, 'add_transaction.html', {'form': form, 'transaction_type': 'expenditure'})


@login_required
def manage_categories(request):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can manage categories.')
        return redirect('dashboard')

    from django.db.models import Count
    
    # Annotate categories with transaction counts
    income_categories = IncomeCategory.objects.select_related('branch', 'created_by')\
        .filter(is_active=True)\
        .annotate(transaction_count=Count('transaction'))\
        .order_by('-transaction_count', 'name')
    
    expenditure_categories = ExpenditureCategory.objects.select_related('branch', 'created_by')\
        .filter(is_active=True)\
        .annotate(transaction_count=Count('transaction'))\
        .order_by('-transaction_count', 'name')
    
    branches = Branch.objects.filter(is_active=True).order_by('name')
    
    # Calculate statistics
    total_income_categories = income_categories.count()
    total_expenditure_categories = expenditure_categories.count()
    total_income_transactions = sum(cat.transaction_count for cat in income_categories)
    total_expenditure_transactions = sum(cat.transaction_count for cat in expenditure_categories)

    return render(request, 'manage_categories.html', {
        'income_categories': income_categories,
        'expenditure_categories': expenditure_categories,
        'branches': branches,
        'total_income_categories': total_income_categories,
        'total_expenditure_categories': total_expenditure_categories,
        'total_income_transactions': total_income_transactions,
        'total_expenditure_transactions': total_expenditure_transactions,
    })


@login_required
def add_income_category(request):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can create categories.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = IncomeCategoryForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.save(commit=False)
            category.created_by = request.user

            # Super admin can set scope and branch
            branch = form.cleaned_data.get('branch')
            if branch:
                category.branch = branch

            category.save()
            messages.success(request, 'Income category added successfully!')
            return redirect('manage_categories')
    else:
        form = IncomeCategoryForm(user=request.user)

    return render(request, 'add_category.html', {'form': form, 'category_type': 'Income'})


@login_required
def add_expenditure_category(request):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can create categories.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = ExpenditureCategoryForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.save(commit=False)
            category.created_by = request.user

            # Super admin can set scope and branch
            branch = form.cleaned_data.get('branch')
            if branch:
                category.branch = branch

            category.save()
            messages.success(request, 'Expenditure category added successfully!')
            return redirect('manage_categories')
    else:
        form = ExpenditureCategoryForm(user=request.user)

    return render(request, 'add_category.html', {'form': form, 'category_type': 'Expenditure'})


@login_required
def edit_income_category(request, category_id):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    category = get_object_or_404(IncomeCategory, id=category_id)
    
    if request.method == 'GET':
        # Return category data as JSON for populating the form
        return JsonResponse({
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'scope': category.scope,
            'branch': category.branch.id if category.branch else None,
        })
    
    if request.method == 'POST':
        form = IncomeCategoryForm(request.POST, user=request.user, instance=category)
        if form.is_valid():
            category = form.save(commit=False)
            branch = form.cleaned_data.get('branch')
            if branch:
                category.branch = branch
            else:
                category.branch = None
            category.save()
            return JsonResponse({'success': True, 'message': 'Income category updated successfully!'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def edit_expenditure_category(request, category_id):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    category = get_object_or_404(ExpenditureCategory, id=category_id)
    
    if request.method == 'GET':
        # Return category data as JSON for populating the form
        return JsonResponse({
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'scope': category.scope,
            'branch': category.branch.id if category.branch else None,
        })
    
    if request.method == 'POST':
        form = ExpenditureCategoryForm(request.POST, user=request.user, instance=category)
        if form.is_valid():
            category = form.save(commit=False)
            branch = form.cleaned_data.get('branch')
            if branch:
                category.branch = branch
            else:
                category.branch = None
            category.save()
            return JsonResponse({'success': True, 'message': 'Expenditure category updated successfully!'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def delete_income_category(request, category_id):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can delete categories.')
        return redirect('manage_categories')
    
    category = get_object_or_404(IncomeCategory, id=category_id)
    
    if request.method == 'POST':
        category_name = category.name
        # Check if category is used in transactions (including fund allocation transactions)
        transaction_count = Transaction.objects.filter(income_category=category).count()
        
        if transaction_count > 0:
            # Check if any are fund allocation transactions
            fund_allocation_count = Transaction.objects.filter(
                income_category=category, 
                fund_allocation__isnull=False
            ).count()
            regular_count = transaction_count - fund_allocation_count
            
            error_msg = f"❌ Cannot Delete Income Category!\n\n" \
                       f'"{category_name}" cannot be deleted because it is used in {transaction_count} transaction(s):\n'
            
            if fund_allocation_count > 0:
                error_msg += f"• {fund_allocation_count} fund allocation transaction(s) (protected)\n"
            if regular_count > 0:
                error_msg += f"• {regular_count} regular income transaction(s)\n"
            
            error_msg += "\nCategories with transactions cannot be deleted to preserve financial integrity and audit trail.\n\n" \
                        "You can:\n" \
                        "• Mark the category as inactive instead (hides from new transactions)\n" \
                        "• Keep it for historical reference"
            
            messages.error(request, error_msg)
            return redirect('manage_categories')
        
        category.delete()
        messages.success(request, f'Income category "{category_name}" deleted successfully!')
        return redirect('manage_categories')
    
    return redirect('manage_categories')


@login_required
def delete_expenditure_category(request, category_id):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can delete categories.')
        return redirect('manage_categories')
    
    category = get_object_or_404(ExpenditureCategory, id=category_id)
    
    if request.method == 'POST':
        category_name = category.name
        # Check if category is used in transactions (including fund allocation transactions)
        transaction_count = Transaction.objects.filter(expenditure_category=category).count()
        
        if transaction_count > 0:
            # Check if any are fund allocation transactions
            fund_allocation_count = Transaction.objects.filter(
                expenditure_category=category, 
                fund_allocation__isnull=False
            ).count()
            regular_count = transaction_count - fund_allocation_count
            
            error_msg = f"❌ Cannot Delete Expenditure Category!\n\n" \
                       f'"{category_name}" cannot be deleted because it is used in {transaction_count} transaction(s):\n'
            
            if fund_allocation_count > 0:
                error_msg += f"• {fund_allocation_count} fund allocation transaction(s) (protected)\n"
            if regular_count > 0:
                error_msg += f"• {regular_count} regular expenditure transaction(s)\n"
            
            error_msg += "\nCategories with transactions cannot be deleted to preserve financial integrity and audit trail.\n\n" \
                        "You can:\n" \
                        "• Mark the category as inactive instead (hides from new transactions)\n" \
                        "• Keep it for historical reference"
            
            messages.error(request, error_msg)
            return redirect('manage_categories')
        
        category.delete()
        messages.success(request, f'Expenditure category "{category_name}" deleted successfully!')
        return redirect('manage_categories')
    
    return redirect('manage_categories')


# New views for delete functionality and user management

@login_required
def delete_branch(request, branch_id):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can delete branches.')
        return redirect('dashboard')

    branch = get_object_or_404(Branch, id=branch_id)

    if branch.branch_type == 'main':
        messages.error(request, 'Cannot delete the main branch.')
        return redirect('manage_branches')

    # Check for fund allocations (both sent and received)
    allocations_made = branch.fund_allocations_made.count()
    allocations_received = branch.fund_allocations_received.count()
    active_allocations_made = branch.fund_allocations_made.filter(is_active=True).count()
    active_allocations_received = branch.fund_allocations_received.filter(is_active=True).count()
    
    total_allocations = allocations_made + allocations_received
    total_active_allocations = active_allocations_made + active_allocations_received
    
    # BLOCK deletion if there are ANY fund allocations (active or reversed)
    if total_allocations > 0:
        messages.error(request,
            f"❌ Cannot Delete Branch with Fund Allocations!\n\n"
            f'"{branch.name}" cannot be deleted because it has {total_allocations} fund allocation(s) '
            f'({total_active_allocations} active, {total_allocations - total_active_allocations} reversed).\n\n'
            f"For financial integrity and audit compliance, branches with fund allocation history CANNOT be deleted.\n\n"
            f"If you need to correct allocation errors:\n"
            f"• Use the 'REVERSE' button on the Fund Allocations page\n"
            f"• This maintains complete audit trail\n\n"
            f"If you need to deactivate this branch:\n"
            f"• Mark it as inactive instead of deleting it\n"
            f"• This preserves all historical financial data"
        )
        return redirect('manage_branches')

    if request.method == 'POST':
        branch_name = branch.name
        transaction_count = branch.transactions.count()
        
        try:
            branch.delete()
            messages.success(request, 
                f'Branch "{branch_name}" deleted successfully!\n'
                f'{transaction_count} transaction(s) were also deleted.'
            )
        except Exception as e:
            messages.error(request, f'Error deleting branch: {str(e)}')
        
        return redirect('manage_branches')

    # Check for related data for confirmation page
    transaction_count = branch.transactions.count()

    return render(request, 'confirm_delete.html', {
        'object_name': f'Branch "{branch.name}"',
        'object_type': 'branch',
        'related_data': {
            'Transactions': transaction_count,
        },
        'warning': 'Deleting this branch will also delete all related transactions.',
        'delete_url': request.path
    })


@login_required
def delete_user(request, user_id):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can delete users.')
        return redirect('dashboard')

    user = get_object_or_404(User, id=user_id)

    if user.user_type == 'chief_accountant':
        messages.error(request, 'Cannot delete super admin users.')
        return redirect('manage_users')

    if request.method == 'POST':
        user_name = user.get_full_name()
        user.delete()
        messages.success(request, f'User "{user_name}" deleted successfully!')
        return redirect('manage_users')

    # Check for related data
    transaction_count = user.transaction_set.count()
    branch_count = user.managed_branches.count()

    return render(request, 'confirm_delete.html', {
        'object_name': f'User "{user.get_full_name()}"',
        'object_type': 'user',
        'related_data': {
            'Transactions': transaction_count,
            'Managed Branches': branch_count,
        },
        'warning': 'Deleting this user will transfer their created transactions to your account.',
        'delete_url': request.path
    })


@login_required
def delete_transaction(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)

    # Check permissions
    if request.user.user_type in ['admin', 'chief_accountant']:
        pass  # Super admin can delete any transaction
    elif request.user.user_type == 'branch_admin':
        if transaction.branch != request.user.managed_branch:
            messages.error(request, 'You can only delete transactions from your branch.')
            return redirect('transactions')
    else:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')

    if request.method == 'POST':
        transaction_desc = f'"{transaction.description}" (₦{transaction.amount:,.2f})'
        transaction.delete()
        messages.success(request, f'Transaction {transaction_desc} deleted successfully!')
        return redirect('transactions')

    return render(request, 'confirm_delete.html', {
        'object_name': f'Transaction: {transaction.description}',
        'object_type': 'transaction',
        'details': f'Amount: ₦{transaction.amount:,.2f}, Date: {transaction.date}, Branch: {transaction.branch.name}',
        'warning': 'This action cannot be undone.',
        'delete_url': request.path
    })


@login_required
def toggle_user_status(request, user_id):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can change user status.')
        return redirect('dashboard')

    user = get_object_or_404(User, id=user_id)

    if user.user_type == 'chief_accountant':
        messages.error(request, 'Cannot change status of super admin users.')
        return redirect('manage_users')

    user.is_active = not user.is_active
    user.save()

    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User "{user.get_full_name()}" {status} successfully!')
    return redirect('manage_users')


@login_required
def reset_user_password(request, user_id):
    if request.user.user_type not in ['admin', 'chief_accountant']:
        messages.error(request, 'Only Chief Accountant can reset passwords.')
        return redirect('dashboard')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        if len(new_password) < 4:
            messages.error(request, 'Password must be at least 4 characters long.')
            return render(request, 'reset_password.html', {'user': user})

        user.set_password(new_password)
        user.save()

        messages.success(request, f'Password for "{user.get_full_name()}" reset successfully!')
        return redirect('manage_users')

    return render(request, 'reset_password.html', {'user': user})


@login_required
def reports(request):
    from datetime import datetime, timedelta
    from django.db.models import Count, Avg
    
    # Get date range filters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    report_type = request.GET.get('report_type', 'overview')
    branch_filter = request.GET.get('branch')
    
    # Default to current month if no dates provided
    if not start_date:
        start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    # Convert to date objects for filtering
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Base queryset for transactions in date range
    transactions_qs = Transaction.objects.filter(
        date__range=[start_date_obj, end_date_obj],
        branch__is_active=True
    )
    
    # Filter by user type and branch
    if request.user.user_type in ['admin', 'chief_accountant']:
        # Super admin can see all branches or filter by specific branch
        branches = Branch.objects.filter(is_active=True).order_by('name')
        if branch_filter:
            transactions_qs = transactions_qs.filter(branch_id=branch_filter)
    else:
        # Branch admin can only see their own branch
        branch = request.user.managed_branch
        if branch:
            transactions_qs = transactions_qs.filter(branch=branch)
        else:
            transactions_qs = Transaction.objects.none()
        branches = None
    
    # Calculate financial metrics
    total_income = transactions_qs.filter(transaction_type='income').aggregate(
        Sum('amount'))['amount__sum'] or Decimal('0')
    total_expenditure = transactions_qs.filter(transaction_type='expenditure').aggregate(
        Sum('amount'))['amount__sum'] or Decimal('0')
    net_balance = total_income - total_expenditure
    
    # Transaction counts
    income_count = transactions_qs.filter(transaction_type='income').count()
    expenditure_count = transactions_qs.filter(transaction_type='expenditure').count()
    total_transactions = income_count + expenditure_count
    
    # Calculate average transaction value
    average_transaction_value = Decimal('0')
    if total_transactions > 0:
        total_amount = total_income + total_expenditure
        average_transaction_value = total_amount / total_transactions
    
    # Daily transaction trends (last 30 days)
    daily_trends = []
    for i in range(30):
        date = datetime.now().date() - timedelta(days=i)
        day_income = transactions_qs.filter(
            transaction_type='income', 
            date=date
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        day_expenditure = transactions_qs.filter(
            transaction_type='expenditure', 
            date=date
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        daily_trends.append({
            'date': date,
            'income': day_income,
            'expenditure': day_expenditure,
            'net': day_income - day_expenditure
        })
    
    # Top categories
    income_categories = transactions_qs.filter(transaction_type='income').values(
        'income_category__name'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')[:5]
    
    expenditure_categories = transactions_qs.filter(transaction_type='expenditure').values(
        'expenditure_category__name'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')[:5]
    
    # Branch performance (super admin only)
    branch_performance = []
    if request.user.user_type in ['admin', 'chief_accountant']:
        branches = Branch.objects.filter(is_active=True)
        for branch in branches:
            branch_transactions = transactions_qs.filter(branch=branch)
            branch_income = branch_transactions.filter(transaction_type='income').aggregate(
                Sum('amount'))['amount__sum'] or Decimal('0')
            branch_expenditure = branch_transactions.filter(transaction_type='expenditure').aggregate(
                Sum('amount'))['amount__sum'] or Decimal('0')
            branch_performance.append({
                'branch': branch,
                'income': branch_income,
                'expenditure': branch_expenditure,
                'net': branch_income - branch_expenditure,
                'transaction_count': branch_transactions.count()
            })
    
    # Recent transactions
    recent_transactions = transactions_qs.select_related(
        'branch', 'created_by', 'income_category', 'expenditure_category'
    ).order_by('-created_date')[:10]
    
    # Monthly comparison (current vs previous month)
    current_month_start = datetime.now().replace(day=1).date()
    previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    previous_month_end = current_month_start - timedelta(days=1)
    
    current_month_income = transactions_qs.filter(
        transaction_type='income',
        date__gte=current_month_start
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    previous_month_income = Transaction.objects.filter(
        transaction_type='income',
        date__range=[previous_month_start, previous_month_end],
        branch__is_active=True
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    income_growth = 0
    if previous_month_income > 0:
        income_growth = ((current_month_income - previous_month_income) / previous_month_income) * 100
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'report_type': report_type,
        'branches': branches,
        'selected_branch': branch_filter,
        'total_income': total_income,
        'total_expenditure': total_expenditure,
        'net_balance': net_balance,
        'income_count': income_count,
        'expenditure_count': expenditure_count,
        'total_transactions': total_transactions,
        'average_transaction_value': average_transaction_value,
        'daily_trends': daily_trends,
        'income_categories': income_categories,
        'expenditure_categories': expenditure_categories,
        'branch_performance': branch_performance,
        'recent_transactions': recent_transactions,
        'current_month_income': current_month_income,
        'previous_month_income': previous_month_income,
        'income_growth': income_growth,
    }
    
    return render(request, 'reports.html', context)


@login_required
def edit_transaction(request, transaction_id):
    """
    Edit transaction - super admin only
    
    IMPORTANT: This function affects branch balances and all financial calculations.
    The accounting system is interdependent:
    - Branch balance = Total Income - Total Expenditure
    - Editing a transaction automatically recalculates all balances
    - All reports and statistics are dynamically computed from transactions
    - Changes to amount, type, or branch will affect financial integrity
    
    PROTECTED: Transactions linked to fund allocations CANNOT be edited.
    """
    if request.user.user_type not in ['admin', 'chief_accountant']:
        return JsonResponse({'success': False, 'message': 'Unauthorized access'}, status=403)
    
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        # BLOCK editing of transactions linked to fund allocations
        if transaction.fund_allocation:
            return JsonResponse({
                'success': False, 
                'message': (
                    "❌ Cannot Edit Fund Allocation Transaction!\n\n"
                    f"This transaction is part of Fund Allocation #{transaction.fund_allocation.id}.\n\n"
                    "Transactions created by fund allocations are PROTECTED and cannot be edited directly.\n\n"
                    "To correct allocation errors:\n"
                    "• Go to the 'Fund Allocations' page\n"
                    "• Click the 'REVERSE' button for the allocation\n"
                    "• This will properly reverse both the income and expenditure transactions\n\n"
                    "This protection ensures fund allocation integrity and maintains audit trail."
                )
            }, status=403)
            
    except Transaction.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Transaction not found'}, status=404)
    
    if request.method == 'GET':
        # Return transaction data as JSON for modal
        data = {
            'success': True,
            'transaction': {
                'id': transaction.id,
                'date': transaction.date.strftime('%Y-%m-%d'),
                'description': transaction.description,
                'amount': str(transaction.amount),
                'transaction_type': transaction.transaction_type,
                'branch': transaction.branch.id if transaction.branch else None,
                'income_category': transaction.income_category.id if transaction.income_category else None,
                'expenditure_category': transaction.expenditure_category.id if transaction.expenditure_category else None,
            }
        }
        return JsonResponse(data)
    
    elif request.method == 'POST':
        # Update transaction with validation to prevent negative balances
        try:
            old_amount = transaction.amount
            old_type = transaction.transaction_type
            old_branch = transaction.branch
            
            new_amount = Decimal(request.POST.get('amount'))
            transaction.date = request.POST.get('date')
            transaction.description = request.POST.get('description')
            
            # Update branch
            branch_id = request.POST.get('branch')
            if branch_id:
                new_branch = Branch.objects.get(id=branch_id)
            else:
                new_branch = old_branch
            
            # VALIDATE: Check if the change would cause negative balance
            # Calculate the impact on balance
            if transaction.transaction_type == 'income':
                # If reducing income, check if balance would go negative
                if new_amount < old_amount:
                    impact = old_amount - new_amount
                    current_balance = new_branch.get_balance()
                    new_balance = current_balance - impact
                    
                    if new_balance < 0:
                        return JsonResponse({
                            'success': False, 
                            'message': f"❌ Cannot reduce income!\n\nReducing this income from ₦{old_amount:,.2f} to ₦{new_amount:,.2f} would result in a negative balance of ₦{new_balance:,.2f}.\n\nCurrent Balance: ₦{current_balance:,.2f}\nReduction Impact: -₦{impact:,.2f}\nResulting Balance: ₦{new_balance:,.2f}\n\nThis system does NOT allow negative balances."
                        }, status=400)
            else:  # expenditure
                # If increasing expenditure, check if balance would go negative
                if new_amount > old_amount:
                    impact = new_amount - old_amount
                    current_balance = new_branch.get_balance()
                    new_balance = current_balance - impact
                    
                    if new_balance < 0:
                        return JsonResponse({
                            'success': False, 
                            'message': f"❌ Cannot increase expenditure!\n\nIncreasing this expenditure from ₦{old_amount:,.2f} to ₦{new_amount:,.2f} would result in a negative balance of ₦{new_balance:,.2f}.\n\nCurrent Balance: ₦{current_balance:,.2f}\nAdditional Expenditure: ₦{impact:,.2f}\nResulting Balance: ₦{new_balance:,.2f}\n\nThis system does NOT allow negative balances. Please ensure sufficient funds before increasing expenditure."
                        }, status=400)
            
            # If validation passed, proceed with update
            transaction.amount = new_amount
            transaction.branch = new_branch
            
            # Update categories based on transaction type
            if transaction.transaction_type == 'income':
                income_category_id = request.POST.get('income_category')
                if income_category_id:
                    transaction.income_category = IncomeCategory.objects.get(id=income_category_id)
                else:
                    transaction.income_category = None
                transaction.expenditure_category = None
            else:
                expenditure_category_id = request.POST.get('expenditure_category')
                if expenditure_category_id:
                    transaction.expenditure_category = ExpenditureCategory.objects.get(id=expenditure_category_id)
                else:
                    transaction.expenditure_category = None
                transaction.income_category = None
            
            transaction.save()
            
            return JsonResponse({'success': True, 'message': 'Transaction updated successfully'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)


@login_required
def delete_transaction(request, transaction_id):
    """
    Delete transaction - super admin only
    
    IMPORTANT: This function affects branch balances and all financial calculations.
    The accounting system is interdependent:
    - Deleting an income transaction REDUCES the branch balance
    - Deleting an expenditure transaction INCREASES the branch balance
    - All reports and statistics are dynamically computed from transactions
    - This operation cannot be undone and affects financial integrity
    
    PROTECTED: Transactions linked to fund allocations CANNOT be deleted.
    """
    if request.user.user_type not in ['admin', 'chief_accountant']:
        return JsonResponse({'success': False, 'message': 'Unauthorized access'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)
    
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        # BLOCK deletion of transactions linked to fund allocations
        if transaction.fund_allocation:
            allocation = transaction.fund_allocation
            return JsonResponse({
                'success': False, 
                'message': (
                    "❌ Cannot Delete Fund Allocation Transaction!\n\n"
                    f"This {transaction.transaction_type} transaction is part of Fund Allocation #{allocation.id}:\n"
                    f"• From: {allocation.from_branch.name}\n"
                    f"• To: {allocation.to_branch.name}\n"
                    f"• Amount: ₦{allocation.amount:,.2f}\n\n"
                    "Transactions created by fund allocations are PROTECTED and cannot be deleted directly.\n\n"
                    "To correct allocation errors:\n"
                    "• Go to the 'Fund Allocations' page\n"
                    "• Find the allocation (#{allocation.id})\n"
                    "• Click the 'REVERSE' button\n"
                    "• This will properly reverse BOTH transactions (income + expenditure)\n\n"
                    "This protection ensures fund allocation integrity and maintains audit trail."
                )
            }, status=403)
        
        # VALIDATE: Check if deleting this transaction would cause negative balance
        branch = transaction.branch
        current_balance = branch.get_balance()
        
        if transaction.transaction_type == 'income':
            # Deleting income reduces the balance
            new_balance = current_balance - transaction.amount
            
            if new_balance < 0:
                return JsonResponse({
                    'success': False, 
                    'message': f"❌ Cannot delete this income transaction!\n\nDeleting this income of ₦{transaction.amount:,.2f} would result in a negative balance of ₦{new_balance:,.2f}.\n\nCurrent Balance: ₦{current_balance:,.2f}\nIncome to Delete: ₦{transaction.amount:,.2f}\nResulting Balance: ₦{new_balance:,.2f}\n\nThis system does NOT allow negative balances. You must first add more income or reduce expenditures before deleting this transaction."
                }, status=400)
        # Note: Deleting expenditure always increases balance, so no validation needed
        
        transaction.delete()
        return JsonResponse({'success': True, 'message': 'Transaction deleted successfully'})
    except Transaction.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Transaction not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
