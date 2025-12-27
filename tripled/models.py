
from django.db import models
import random
import string
from django.utils import timezone
import uuid
from decimal import Decimal
from django.contrib.auth.models import AbstractUser

import os

class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('admin', 'Admin'),
        ('secretary', 'Secretary'),
        ('chief_accountant', 'Chief Accountant'),  # For accounting system - full access
        ('branch_admin', 'Branch Admin'),          # For accounting system - branch level
    ]
    
    date_joined = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to='users/', null=True, blank=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='admin')
    phone = models.CharField(max_length=15, blank=True, null=True)
    
    def __str__(self):
        return self.username
    
    def get_full_name(self):
        """Return full name for accounting compatibility"""
        return f"{self.first_name} {self.last_name}".strip() or self.username
    
    @property
    def managed_branch(self):
        """Get the first branch this user manages (for accounting)"""
        if hasattr(self, 'managed_branches'):
            return self.managed_branches.filter(is_active=True).first()
        return None

    class Meta:
        app_label = 'tripled'




class Realtor(models.Model):
    # Status choices
    STATUS_CHOICES = [
        ('regular', 'Regular Realtor'),
        ('executive', 'Executive Realtor'),
    ]
    
    # Profile Information
    first_name = models.CharField(max_length=100,blank=True, null=True)
    last_name = models.CharField(max_length=100,blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    phone = models.CharField(max_length=20,blank=True, null=True)
    image = models.ImageField(upload_to='realtors/', blank=True, null=True)
    address = models.CharField(max_length=255,blank=True, null=True)
    country = models.CharField(max_length=100,blank=True, null=True)
    
    # Status field - can be changed by admin
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='regular',
        help_text="Realtor status - can be changed by admin"
    )
    
    # Banking Details
    account_number = models.CharField(max_length=50,blank=True, null=True)
    bank_name = models.CharField(max_length=100,blank=True, null=True)
    account_name = models.CharField(max_length=100,blank=True, null=True)
    
    
    # Referral System
    referral_code = models.CharField(max_length=8, unique=True)
    sponsor_code = models.CharField(max_length=8, blank=True, null=True)
    sponsor = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, related_name='referrals')
    
    # Commission Tracking
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    paid_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def unpaid_commission(self):
        """Calculate unpaid commission amount"""
        return self.total_commission - self.paid_commission
    
    @property
    def full_name(self):
        """Return the realtor's full name"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_executive(self):
        """Check if realtor is an executive"""
        return self.status == 'executive'
    
    # @property
    # def status_display(self):
    #     """Return human-readable status"""
    #     return dict(self.STATUS_CHOICES)[self.status]
    @property
    def status_display(self):
        """Return human-readable status"""
        status_dict = dict(self.STATUS_CHOICES)
        return status_dict.get(self.status, self.status.title())
    
    @property
    def image_url(self):
        """Return image URL or default image URL"""
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        else:
            from django.conf import settings
            return f"{settings.STATIC_URL}user/images/default_profile.jpg"
        
    def promote_to_executive(self):
        """Promote realtor to executive status"""
        self.status = 'executive'
        self.save()
    
    def demote_to_regular(self):
        """Demote realtor to regular status"""
        self.status = 'regular'
        self.save()
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Generate unique referral code for new realtors
        if not self.referral_code:
            self.referral_code = self._generate_unique_code()
        
        # Link to sponsor if sponsor_code is provided
        if self.sponsor_code and not self.sponsor:
            try:
                self.sponsor = Realtor.objects.get(referral_code=self.sponsor_code)
            except Realtor.DoesNotExist:
                pass  # Handle invalid sponsor code (could log this)
                
        super().save(*args, **kwargs)
        
        # CRITICAL: Verify ID was assigned after save
        if not self.pk:
            raise ValueError("Realtor object was saved but did not receive an ID. This should never happen.")
    
    def _generate_unique_code(self):
        """Generate a unique 8-digit numeric referral code"""
        while True:
            # Generate 8-digit numeric code
            code = ''.join(random.choices(string.digits, k=8))
            # Check if code already exists
            if not Realtor.objects.filter(referral_code=code).exists():
                return code
    
    class Meta:
        ordering = ['status', 'last_name', 'first_name']  # Executive realtors first
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['referral_code']),
        ]
    
    def __str__(self):
        return f"{self.full_name} ({self.status_display})"




class Commission(models.Model):
    """Model to track individual commission transactions"""
    realtor = models.ForeignKey(Realtor, on_delete=models.CASCADE, related_name='commissions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)  # e.g., "Commission for Property XYZ sale"
    property_reference = models.CharField(max_length=100, blank=True, null=True)  # Reference to property sold
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # CRITICAL: Verify ID was assigned after save
        if not self.pk:
            raise ValueError("Commission object was saved but did not receive an ID. This should never happen.")
    
    def mark_as_paid(self):
        """Mark this commission as paid and update the realtor's paid_commission"""
        if not self.is_paid:
            self.is_paid = True
            self.paid_date = timezone.now()
            self.save()
            
            # Update realtor's paid commission
            self.realtor.paid_commission += self.amount
            self.realtor.save()
    
    def __str__(self):
        status = "Paid" if self.is_paid else "Unpaid"
        return f"{self.realtor.full_name} - ${self.amount} ({status})"


class Property(models.Model):
    STATES_CHOICES = [
        ('abia', 'Abia'),
        ('adamawa', 'Adamawa'),
        ('akwa_ibom', 'Akwa Ibom'),
        ('anambra', 'Anambra'),
        ('bauchi', 'Bauchi'),
        ('bayelsa', 'Bayelsa'),
        ('benue', 'Benue'),
        ('borno', 'Borno'),
        ('cross_river', 'Cross River'),
        ('delta', 'Delta'),
        ('ebonyi', 'Ebonyi'),
        ('edo', 'Edo'),
        ('ekiti', 'Ekiti'),
        ('enugu', 'Enugu'),
        ('fct', 'Federal Capital Territory'),
        ('gombe', 'Gombe'),
        ('imo', 'Imo'),
        ('jigawa', 'Jigawa'),
        ('kaduna', 'Kaduna'),
        ('kano', 'Kano'),
        ('katsina', 'Katsina'),
        ('kebbi', 'Kebbi'),
        ('kogi', 'Kogi'),
        ('kwara', 'Kwara'),
        ('lagos', 'Lagos'),
        ('nasarawa', 'Nasarawa'),
        ('niger', 'Niger'),
        ('ogun', 'Ogun'),
        ('ondo', 'Ondo'),
        ('osun', 'Osun'),
        ('oyo', 'Oyo'),
        ('plateau', 'Plateau'),
        ('rivers', 'Rivers'),
        ('sokoto', 'Sokoto'),
        ('taraba', 'Taraba'),
        ('yobe', 'Yobe'),
        ('zamfara', 'Zamfara'),
    ]
    
    name = models.CharField(max_length=255,blank=True, null=True)
    description = models.TextField()
    location = models.CharField(max_length=100, choices=STATES_CHOICES)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # CRITICAL: Verify ID was assigned after save
        if not self.pk:
            raise ValueError("Property object was saved but did not receive an ID. This should never happen.")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Properties"



class PropertySale(models.Model):
    PROPERTY_TYPE_CHOICES = [
        ('building', 'Building Property'),
        ('land', 'Land'),
    ]
    
    PAYMENT_PLAN_CHOICES = [
        ('outright', 'Outright Purchase'),
        ('3_months', '3 Months Plan'),
        ('6_months', '6 Months Plan'),
    ]
    
    MARITAL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
    ]
    
    ID_TYPE_CHOICES = [
        ('national_id', 'National ID'),
        ('intl_passport', 'International Passport'),
        ('drivers_license', 'Driver\'s License'),
        ('voters_card', 'Voter\'s Card'),
    ]
    
    # Generate a unique reference number
    @staticmethod
    def generate_reference_number():
        """Generate a unique 12-character uppercase reference number"""
        return ''.join(uuid.uuid4().hex[:12].upper())
    
    reference_number = models.CharField(max_length=12, unique=True, editable=False, blank=True)
    description = models.TextField(max_length=255)
    property_type = models.CharField(max_length=10, choices=PROPERTY_TYPE_CHOICES)
    property_item = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='sales')  # Renamed from 'property'
    quantity = models.PositiveIntegerField(help_text="Number of plots or buildings")
    
    # Client information
    client_name = models.CharField(max_length=255, blank=True, null=True)
    client_address = models.TextField( blank=True, null=True)
    client_phone = models.CharField(max_length=20, blank=True, null=True)
    client_email = models.EmailField(max_length=255, blank=True, null=True)
    # Add to client information section
    client_picture = models.ImageField(upload_to='client_pictures/', blank=True, null=True, )

    
    
    # Client additional information
    marital_status = models.CharField(max_length=10, choices=MARITAL_STATUS_CHOICES, default='single')
    spouse_name = models.CharField(max_length=255, blank=True, null=True)
    spouse_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Client identification
    id_type = models.CharField(max_length=15, choices=ID_TYPE_CHOICES, blank=True, null=True)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Plot development timeline
    plot_development_start_date = models.DateField(blank=True, null=True)
    plot_development_expiry_date = models.DateField(blank=True, null=True)
    # ADD THIS NEW FIELD
    is_developed = models.BooleanField(default=False, help_text="Mark as True when client has developed the property")
    
    # Client origin
    lga_of_origin = models.CharField(max_length=100, blank=True, null=True)
    town_of_origin = models.CharField(max_length=100, blank=True, null=True)
    state_of_origin = models.CharField(max_length=100, blank=True, null=True)
    
    # Client bank details
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    account_number = models.CharField(max_length=20, blank=True, null=True)
    account_name = models.CharField(max_length=255, blank=True, null=True)
    
    # Next of kin information
    next_of_kin_name = models.CharField(max_length=255, blank=True, null=True)
    next_of_kin_address = models.TextField( blank=True, null=True)
    next_of_kin_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Pricing information
    original_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Payment plan
    payment_plan = models.CharField(max_length=10, choices=PAYMENT_PLAN_CHOICES, default='outright')
    
    # Realtor and commission tracking
    realtor = models.ForeignKey(Realtor, on_delete=models.CASCADE, related_name='sales')
    realtor_commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sponsor_commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    upline_commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Track who created this sale (admin or secretary)
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_property_sales', verbose_name='Created By')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.reference_number} - {self.client_name}"
    
    @property
    def balance_due(self):
        """Calculate the remaining balance to be paid"""
        return self.selling_price - self.amount_paid
    
    @property
    def is_fully_paid(self):
        """Check if the property is fully paid for"""
        return self.balance_due <= Decimal('0')
    
    # ADD THIS NEW PROPERTY METHOD
    @property
    def development_status(self):
        """
        Get the development status based on timeline and development flag
        Returns: 'developed', 'expired', 'expiring', 'valid', or 'no_timeline'
        """
        from django.utils import timezone
        from datetime import timedelta
        
        # If already developed, return developed status
        if self.is_developed:
            return 'developed'
        
        # If no expiry date set, return no timeline
        if not self.plot_development_expiry_date:
            return 'no_timeline'
        
        today = timezone.now().date()
        expiry_date = self.plot_development_expiry_date
        
        # If expired
        if today > expiry_date:
            return 'expired'
        
        # If expiring within 30 days
        days_to_expiry = (expiry_date - today).days
        if days_to_expiry <= 180:
            return 'expiring'
        
        # If still valid
        return 'valid'
    
    @property 
    def development_status_display(self):
        """Get human readable development status"""
        status_map = {
            'developed': 'Developed',
            'expired': 'Timeline Expired',
            'expiring': 'Expiring Soon',
            'valid': 'Timeline Valid',
            'no_timeline': 'No Timeline Set'
        }
        return status_map.get(self.development_status, 'Unknown')
    
    @property
    def development_status_class(self):
        """Get CSS class for development status styling"""
        status_class_map = {
            'developed': 'badge-success',
            'expired': 'badge-danger', 
            'expiring': 'badge-warning',
            'valid': 'badge-info',
            'no_timeline': 'badge-secondary'
        }
        return status_class_map.get(self.development_status, 'badge-secondary')
    
    def calculate_commission(self):
        """Calculate and distribute commission based on the amount paid"""
        if self.amount_paid <= Decimal('0'):
            return
        
        # Get the previously paid amount before this update
        try:
            previous_paid = PropertySale.objects.get(pk=self.pk).amount_paid if self.pk else Decimal('0')
        except PropertySale.DoesNotExist:
            previous_paid = Decimal('0')
        
        # Only calculate commission on the new payment amount
        new_payment_amount = self.amount_paid - previous_paid
        
        if new_payment_amount <= Decimal('0'):
            return
        
        # Calculate commission amounts based on the new payment amount only
        realtor_commission = (new_payment_amount * self.realtor_commission_percentage) / Decimal('100')
        
        # Create commission for the selling realtor
        commission = Commission.objects.create(
            realtor=self.realtor,
            amount=realtor_commission,
            description=f"Commission for property sale {self.reference_number}",
            property_reference=self.reference_number
        )
        
        # CRITICAL: Verify commission got an ID
        if not commission.pk:
            raise ValueError("Commission object was created but did not receive an ID.")
        
        # Add to realtor's total commission
        self.realtor.total_commission += realtor_commission
        self.realtor.save(update_fields=['total_commission'])
        
        # Process sponsor commission if exists
        if self.realtor.sponsor and self.sponsor_commission_percentage > Decimal('0'):
            sponsor_commission = (new_payment_amount * self.sponsor_commission_percentage) / Decimal('100')
            
            commission = Commission.objects.create(
                realtor=self.realtor.sponsor,
                amount=sponsor_commission,
                description=f"Sponsor commission for property sale {self.reference_number}",
                property_reference=self.reference_number
            )
            
            # CRITICAL: Verify commission got an ID
            if not commission.pk:
                raise ValueError("Sponsor commission object was created but did not receive an ID.")
            
            self.realtor.sponsor.total_commission += sponsor_commission
            self.realtor.sponsor.save(update_fields=['total_commission'])
            
            # Process upline commission if exists
            if self.realtor.sponsor.sponsor and self.upline_commission_percentage > Decimal('0'):
                upline_commission = (new_payment_amount * self.upline_commission_percentage) / Decimal('100')
                
                commission = Commission.objects.create(
                    realtor=self.realtor.sponsor.sponsor,
                    amount=upline_commission,
                    description=f"Upline commission for property sale {self.reference_number}",
                    property_reference=self.reference_number
                )
                
                # CRITICAL: Verify commission got an ID
                if not commission.pk:
                    raise ValueError("Upline commission object was created but did not receive an ID.")
                
                self.realtor.sponsor.sponsor.total_commission += upline_commission
                self.realtor.sponsor.sponsor.save(update_fields=['total_commission'])
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_amount_paid = Decimal('0')
        
        if not is_new:
            try:
                old_instance = PropertySale.objects.get(pk=self.pk)
                old_amount_paid = old_instance.amount_paid
            except PropertySale.DoesNotExist:
                pass
        
        # Ensure reference_number is set before saving
        if not self.reference_number:
            self.reference_number = self.generate_reference_number()
        
        super().save(*args, **kwargs)
        
        # CRITICAL: Verify ID was assigned after save
        if not self.pk:
            raise ValueError("PropertySale object was saved but did not receive an ID. This should never happen.")
        
        # Check if amount_paid has changed
        if is_new or old_amount_paid != self.amount_paid:
            self.calculate_commission()


class Payment(models.Model):
    property_sale = models.ForeignKey(PropertySale, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(blank=True,null=True)
    payment_method = models.CharField(max_length=50, default='Cash')
    reference = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    
    
    def save(self, *args, **kwargs):
        from django.db import transaction
        
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # CRITICAL: Verify ID was assigned after save
        if not self.pk:
            raise ValueError("Payment object was saved but did not receive an ID. This should never happen.")
        
        # Ensure property_sale has an ID before using it
        if not self.property_sale_id:
            raise ValueError("Payment object must have a valid property_sale_id before saving.")
        
        # Only update the property sale's amount_paid if this is a new payment
        if is_new:
            # Use transaction to ensure atomicity and prevent duplicate commission creation
            with transaction.atomic():
                # Recalculate the total from the database to ensure accuracy
                total_payments = Payment.objects.filter(property_sale=self.property_sale).aggregate(
                    models.Sum('amount'))['amount__sum'] or Decimal('0')
                
                # Store the old amount_paid before updating
                old_amount_paid = self.property_sale.amount_paid
                
                # Update the property sale with the accurate total
                self.property_sale.amount_paid = total_payments
                
                # Save without triggering the calculate_commission in PropertySale.save()
                PropertySale.objects.filter(pk=self.property_sale.pk).update(amount_paid=total_payments)
                
                # Calculate commissions directly based on the new payment amount only
                new_payment_amount = self.amount
                
                # Calculate commission amounts based on the new payment amount only
                realtor_commission = (new_payment_amount * self.property_sale.realtor_commission_percentage) / Decimal('100')
                
                # Create commission for the selling realtor only if amount > 0
                if realtor_commission > Decimal('0'):
                    try:
                        commission = Commission.objects.create(
                            realtor=self.property_sale.realtor,
                            amount=realtor_commission,
                            description=f"Commission for payment on sale {self.property_sale.reference_number}",
                            property_reference=self.property_sale.reference_number
                        )
                        
                        # CRITICAL: Verify commission got an ID
                        if not commission.pk:
                            raise ValueError("Commission object was created but did not receive an ID.")
                        
                        # Add to realtor's total commission
                        self.property_sale.realtor.total_commission += realtor_commission
                        self.property_sale.realtor.save(update_fields=['total_commission'])
                    except Exception as e:
                        # Log the error but don't fail the payment
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error creating realtor commission: {e}")
                
                # Process sponsor commission if exists
                if self.property_sale.realtor.sponsor and self.property_sale.sponsor_commission_percentage > Decimal('0'):
                    sponsor_commission = (new_payment_amount * self.property_sale.sponsor_commission_percentage) / Decimal('100')
                    
                    if sponsor_commission > Decimal('0'):
                        try:
                            commission = Commission.objects.create(
                                realtor=self.property_sale.realtor.sponsor,
                                amount=sponsor_commission,
                                description=f"Sponsor commission for payment on sale {self.property_sale.reference_number}",
                                property_reference=self.property_sale.reference_number
                            )
                            
                            # CRITICAL: Verify commission got an ID
                            if not commission.pk:
                                raise ValueError("Sponsor commission object was created but did not receive an ID.")
                            
                            self.property_sale.realtor.sponsor.total_commission += sponsor_commission
                            self.property_sale.realtor.sponsor.save(update_fields=['total_commission'])
                        except Exception as e:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.error(f"Error creating sponsor commission: {e}")
                    
                    # Process upline commission if exists
                    if self.property_sale.realtor.sponsor.sponsor and self.property_sale.upline_commission_percentage > Decimal('0'):
                        upline_commission = (new_payment_amount * self.property_sale.upline_commission_percentage) / Decimal('100')
                        
                        if upline_commission > Decimal('0'):
                            try:
                                commission = Commission.objects.create(
                                    realtor=self.property_sale.realtor.sponsor.sponsor,
                                    amount=upline_commission,
                                    description=f"Upline commission for payment on sale {self.property_sale.reference_number}",
                                    property_reference=self.property_sale.reference_number
                                )
                                
                                # CRITICAL: Verify commission got an ID
                                if not commission.pk:
                                    raise ValueError("Upline commission object was created but did not receive an ID.")
                                
                                self.property_sale.realtor.sponsor.sponsor.total_commission += upline_commission
                                self.property_sale.realtor.sponsor.sponsor.save(update_fields=['total_commission'])
                            except Exception as e:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.error(f"Error creating upline commission: {e}")
    

class General(models.Model):
    
    # Company Bank Information
    company_bank_name = models.CharField(max_length=150,blank=True, null=True)
    company_account_name = models.CharField(max_length=150, blank=True, null=True)
    company_account_number = models.CharField(max_length=150, blank=True, null=True)
    # phone = models.CharField(max_length=20)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # CRITICAL: Verify ID was assigned after save
        if not self.pk:
            raise ValueError("General object was saved but did not receive an ID. This should never happen.")

    def __str__(self):
            return self.company_bank_name
        
        
        
# ==============================================================================

    
# class Gallery(models.Model):
#     """Model for storing gallery images displayed on the frontend"""
    
#     title = models.CharField(max_length=255, blank=True, null=True)
#     description = models.TextField(blank=True, null=True)
#     image = models.ImageField(upload_to='gallery/')
#     order = models.PositiveIntegerField(default=0, help_text="Display order in gallery")
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(default=timezone.now)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         ordering = ['order', '-created_at']
#         verbose_name = 'Gallery Image'
#         verbose_name_plural = 'Gallery Images'
    
#     def __str__(self):
#         return self.title if self.title else f"Gallery Image {self.id}"
    

class SecretaryAdmin(models.Model):
    """Model for secretary admin accounts"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_secretaries')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # CRITICAL: Verify ID was assigned after save
        if not self.pk:
            raise ValueError("SecretaryAdmin object was saved but did not receive an ID. This should never happen.")
    
    class Meta:
        verbose_name = 'Secretary Admin'
        verbose_name_plural = 'Secretary Admins'
        
    def __str__(self):
        return f"{self.full_name} - {self.email}"
    
    
    