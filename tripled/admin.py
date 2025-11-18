from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    User, Realtor, Commission, Property, PropertySale, Payment, General, SecretaryAdmin
)


# Customize User Admin
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model"""
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['date_joined', 'last_login']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profile Image', {'fields': ('image',)}),
    )


# Commission Inline for Realtor
class CommissionInline(admin.TabularInline):
    """Inline admin for Commission model"""
    model = Commission
    extra = 0
    readonly_fields = ['created_at', 'paid_date']
    fields = ['amount', 'description', 'property_reference', 'is_paid', 'paid_date', 'created_at']
    can_delete = False


# Payment Inline for PropertySale
class PaymentInline(admin.TabularInline):
    """Inline admin for Payment model"""
    model = Payment
    extra = 0
    readonly_fields = ['created_at', 'updated_at']
    fields = ['amount', 'payment_date', 'payment_method', 'reference', 'notes', 'created_at']
    can_delete = True


@admin.register(Realtor)
class RealtorAdmin(admin.ModelAdmin):
    """Admin interface for Realtor model"""
    list_display = [
        'full_name_display', 'email', 'phone', 'referral_code', 'status_badge', 
        'total_commission', 'paid_commission', 'unpaid_commission_display', 
        'sponsor_link', 'created_at'
    ]
    list_filter = ['status', 'country', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'referral_code', 'sponsor_code']
    readonly_fields = [
        'referral_code', 'total_commission', 'paid_commission', 'unpaid_commission_display',
        'created_at', 'updated_at', 'image_preview'
    ]
    fieldsets = (
        ('Profile Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'image', 'image_preview', 
                      'address', 'country', 'status')
        }),
        ('Banking Details', {
            'fields': ('bank_name', 'account_name', 'account_number')
        }),
        ('Referral System', {
            'fields': ('referral_code', 'sponsor_code', 'sponsor')
        }),
        ('Commission Information', {
            'fields': ('total_commission', 'paid_commission', 'unpaid_commission_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [CommissionInline]
    
    def full_name_display(self, obj):
        """Display full name"""
        return obj.full_name
    full_name_display.short_description = 'Name'
    full_name_display.admin_order_field = 'first_name'
    
    def status_badge(self, obj):
        """Display status with badge styling"""
        colors = {
            'executive': 'gold',
            'regular': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.status_display
        )
    status_badge.short_description = 'Status'
    
    def unpaid_commission_display(self, obj):
        """Display unpaid commission"""
        return f"₦{obj.unpaid_commission:,.2f}"
    unpaid_commission_display.short_description = 'Unpaid Commission'
    
    def sponsor_link(self, obj):
        """Link to sponsor"""
        if obj.sponsor:
            url = reverse('admin:tripled_realtor_change', args=[obj.sponsor.pk])
            return format_html('<a href="{}">{}</a>', url, obj.sponsor.full_name)
        return '-'
    sponsor_link.short_description = 'Sponsor'
    
    def image_preview(self, obj):
        """Preview realtor image"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px;" />',
                obj.image.url
            )
        return 'No image'
    image_preview.short_description = 'Image Preview'


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    """Admin interface for Commission model"""
    list_display = [
        'realtor_link', 'amount_display', 'description', 'property_reference', 
        'status_badge', 'paid_date', 'created_at'
    ]
    list_filter = ['is_paid', 'created_at', 'paid_date']
    search_fields = ['realtor__first_name', 'realtor__last_name', 'realtor__email', 
                     'description', 'property_reference']
    readonly_fields = ['created_at', 'paid_date']
    date_hierarchy = 'created_at'
    actions = ['mark_as_paid', 'mark_as_unpaid']
    
    fieldsets = (
        ('Commission Details', {
            'fields': ('realtor', 'amount', 'description', 'property_reference')
        }),
        ('Payment Status', {
            'fields': ('is_paid', 'paid_date', 'created_at')
        }),
    )
    
    def realtor_link(self, obj):
        """Link to realtor"""
        url = reverse('admin:tripled_realtor_change', args=[obj.realtor.pk])
        return format_html('<a href="{}">{}</a>', url, obj.realtor.full_name)
    realtor_link.short_description = 'Realtor'
    realtor_link.admin_order_field = 'realtor__first_name'
    
    def amount_display(self, obj):
        """Display amount formatted"""
        return f"₦{obj.amount:,.2f}"
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def status_badge(self, obj):
        """Display payment status"""
        if obj.is_paid:
            return format_html(
                '<span style="background-color: green; color: white; padding: 3px 8px; border-radius: 3px;">Paid</span>'
            )
        return format_html(
            '<span style="background-color: orange; color: white; padding: 3px 8px; border-radius: 3px;">Unpaid</span>'
        )
    status_badge.short_description = 'Status'
    
    def mark_as_paid(self, request, queryset):
        """Mark selected commissions as paid"""
        count = 0
        for commission in queryset.filter(is_paid=False):
            commission.mark_as_paid()
            count += 1
        self.message_user(request, f'{count} commission(s) marked as paid.')
    mark_as_paid.short_description = 'Mark selected commissions as paid'
    
    def mark_as_unpaid(self, request, queryset):
        """Mark selected commissions as unpaid"""
        count = queryset.update(is_paid=False, paid_date=None)
        self.message_user(request, f'{count} commission(s) marked as unpaid.')
    mark_as_unpaid.short_description = 'Mark selected commissions as unpaid'


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    """Admin interface for Property model"""
    list_display = ['name', 'location', 'address_preview', 'sales_count', 'created_at']
    list_filter = ['location', 'created_at']
    search_fields = ['name', 'description', 'address', 'location']
    readonly_fields = ['created_at', 'updated_at', 'sales_count']
    
    fieldsets = (
        ('Property Information', {
            'fields': ('name', 'description', 'location', 'address')
        }),
        ('Statistics', {
            'fields': ('sales_count',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def address_preview(self, obj):
        """Preview of address"""
        if len(obj.address) > 50:
            return obj.address[:50] + '...'
        return obj.address
    address_preview.short_description = 'Address'
    
    def sales_count(self, obj):
        """Count of sales for this property"""
        return obj.sales.count()
    sales_count.short_description = 'Total Sales'


@admin.register(PropertySale)
class PropertySaleAdmin(admin.ModelAdmin):
    """Admin interface for PropertySale model"""
    list_display = [
        'reference_number', 'client_name', 'property_link', 'realtor_link',
        'selling_price_display', 'amount_paid_display', 'balance_due_display',
        'payment_status', 'development_status_badge', 'created_at'
    ]
    list_filter = [
        'property_type', 'payment_plan', 'marital_status', 'is_developed',
        'created_at', 'plot_development_expiry_date'
    ]
    search_fields = [
        'reference_number', 'client_name', 'client_email', 'client_phone',
        'property_item__name', 'realtor__first_name', 'realtor__last_name'
    ]
    readonly_fields = [
        'reference_number', 'balance_due_display', 'is_fully_paid_display',
        'development_status_display', 'created_at', 'updated_at', 'client_picture_preview'
    ]
    date_hierarchy = 'created_at'
    inlines = [PaymentInline]
    
    fieldsets = (
        ('Sale Reference', {
            'fields': ('reference_number',)
        }),
        ('Property Information', {
            'fields': ('property_item', 'property_type', 'quantity', 'description')
        }),
        ('Client Information', {
            'fields': (
                'client_name', 'client_email', 'client_phone', 'client_address',
                'client_picture', 'client_picture_preview', 'marital_status',
                'spouse_name', 'spouse_phone'
            )
        }),
        ('Client Identification', {
            'fields': ('id_type', 'id_number'),
            'classes': ('collapse',)
        }),
        ('Client Origin', {
            'fields': ('state_of_origin', 'lga_of_origin', 'town_of_origin'),
            'classes': ('collapse',)
        }),
        ('Client Bank Details', {
            'fields': ('bank_name', 'account_name', 'account_number'),
            'classes': ('collapse',)
        }),
        ('Next of Kin', {
            'fields': ('next_of_kin_name', 'next_of_kin_address', 'next_of_kin_phone'),
            'classes': ('collapse',)
        }),
        ('Pricing', {
            'fields': (
                'original_price', 'selling_price', 'discount', 'amount_paid',
                'balance_due_display', 'is_fully_paid_display', 'payment_plan'
            )
        }),
        ('Development Timeline', {
            'fields': (
                'plot_development_start_date', 'plot_development_expiry_date',
                'is_developed', 'development_status_display'
            )
        }),
        ('Realtor & Commission', {
            'fields': (
                'realtor', 'realtor_commission_percentage',
                'sponsor_commission_percentage', 'upline_commission_percentage'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def property_link(self, obj):
        """Link to property"""
        url = reverse('admin:tripled_property_change', args=[obj.property_item.pk])
        return format_html('<a href="{}">{}</a>', url, obj.property_item.name)
    property_link.short_description = 'Property'
    
    def realtor_link(self, obj):
        """Link to realtor"""
        url = reverse('admin:tripled_realtor_change', args=[obj.realtor.pk])
        return format_html('<a href="{}">{}</a>', url, obj.realtor.full_name)
    realtor_link.short_description = 'Realtor'
    
    def selling_price_display(self, obj):
        """Display selling price"""
        return f"₦{obj.selling_price:,.2f}"
    selling_price_display.short_description = 'Selling Price'
    selling_price_display.admin_order_field = 'selling_price'
    
    def amount_paid_display(self, obj):
        """Display amount paid"""
        return f"₦{obj.amount_paid:,.2f}"
    amount_paid_display.short_description = 'Amount Paid'
    amount_paid_display.admin_order_field = 'amount_paid'
    
    def balance_due_display(self, obj):
        """Display balance due"""
        return f"₦{obj.balance_due:,.2f}"
    balance_due_display.short_description = 'Balance Due'
    
    def is_fully_paid_display(self, obj):
        """Display if fully paid"""
        if obj.is_fully_paid:
            return format_html('<span style="color: green; font-weight: bold;">✓ Fully Paid</span>')
        return format_html('<span style="color: orange;">Pending</span>')
    is_fully_paid_display.short_description = 'Payment Status'
    
    def payment_status(self, obj):
        """Payment status badge"""
        if obj.is_fully_paid:
            return format_html(
                '<span style="background-color: green; color: white; padding: 3px 8px; border-radius: 3px;">Paid</span>'
            )
        elif obj.amount_paid > 0:
            return format_html(
                '<span style="background-color: orange; color: white; padding: 3px 8px; border-radius: 3px;">Partial</span>'
            )
        return format_html(
            '<span style="background-color: red; color: white; padding: 3px 8px; border-radius: 3px;">Unpaid</span>'
        )
    payment_status.short_description = 'Payment'
    
    def development_status_badge(self, obj):
        """Display development status"""
        status_map = {
            'developed': ('green', 'Developed'),
            'expired': ('red', 'Expired'),
            'expiring': ('orange', 'Expiring'),
            'valid': ('blue', 'Valid'),
            'no_timeline': ('gray', 'No Timeline')
        }
        color, text = status_map.get(obj.development_status, ('gray', 'Unknown'))
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color, text
        )
    development_status_badge.short_description = 'Development'
    
    def client_picture_preview(self, obj):
        """Preview client picture"""
        if obj.client_picture:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px;" />',
                obj.client_picture.url
            )
        return 'No image'
    client_picture_preview.short_description = 'Client Picture Preview'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin interface for Payment model"""
    list_display = [
        'property_sale_link', 'amount_display', 'payment_method', 
        'payment_date', 'reference', 'created_at'
    ]
    list_filter = ['payment_method', 'payment_date', 'created_at']
    search_fields = [
        'property_sale__reference_number', 'property_sale__client_name',
        'reference', 'notes'
    ]
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'payment_date'
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('property_sale', 'amount', 'payment_method', 'payment_date', 'reference', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def property_sale_link(self, obj):
        """Link to property sale"""
        url = reverse('admin:tripled_propertysale_change', args=[obj.property_sale.pk])
        return format_html('<a href="{}">{}</a>', url, obj.property_sale.reference_number)
    property_sale_link.short_description = 'Property Sale'
    
    def amount_display(self, obj):
        """Display amount formatted"""
        return f"₦{obj.amount:,.2f}"
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'


@admin.register(General)
class GeneralAdmin(admin.ModelAdmin):
    """Admin interface for General settings"""
    list_display = ['company_bank_name', 'company_account_name', 'company_account_number', 'id']
    fieldsets = (
        ('Company Bank Information', {
            'fields': ('company_bank_name', 'company_account_name', 'company_account_number')
        }),
    )
    
    def has_add_permission(self, request):
        """Only allow one settings instance"""
        return not General.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of settings"""
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Redirect to edit page if only one object exists"""
        if General.objects.count() == 1:
            obj = General.objects.first()
            from django.shortcuts import redirect
            return redirect(reverse('admin:tripled_general_change', args=[obj.pk]))
        return super().changelist_view(request, extra_context)


@admin.register(SecretaryAdmin)
class SecretaryAdminAdmin(admin.ModelAdmin):
    """Admin interface for SecretaryAdmin model"""
    list_display = [
        'full_name', 'email', 'phone_number', 'user_link', 
        'is_active_badge', 'created_by_link', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['full_name', 'email', 'phone_number', 'user__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Secretary Information', {
            'fields': ('user', 'full_name', 'email', 'phone_number', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        """Link to user"""
        url = reverse('admin:tripled_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User Account'
    
    def is_active_badge(self, obj):
        """Display active status"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: green; color: white; padding: 3px 8px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: red; color: white; padding: 3px 8px; border-radius: 3px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    
    def created_by_link(self, obj):
        """Link to creator"""
        if obj.created_by:
            url = reverse('admin:tripled_user_change', args=[obj.created_by.pk])
            return format_html('<a href="{}">{}</a>', url, obj.created_by.username)
        return '-'
    created_by_link.short_description = 'Created By'


# Customize admin site headers
admin.site.site_header = "Triple D Big Dream Homes Administration"
admin.site.site_title = "Triple D Big Dream Homes Admin"
admin.site.index_title = "Welcome to Triple D Big Dream Homes Administration"
