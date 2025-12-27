# admin.py
from django.contrib import admin
from .models import Branch, IncomeCategory, ExpenditureCategory, FundAllocation, Transaction

# Note: User is managed by tripled.admin, not here


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'location', 'state', 'branch_type', 'allocated_funds', 'is_active', 'created_date', 'created_by',
    )
    list_filter = ('state', 'branch_type', 'is_active', 'admins')
    search_fields = ('name', 'location', 'state', 'address', 'admins__username', 'admins__email')
    readonly_fields = ('created_date',)
    autocomplete_fields = ('created_by',)
    filter_horizontal = ('admins',)
    ordering = ('-created_date',)


@admin.register(IncomeCategory)
class IncomeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'scope', 'branch', 'is_active', 'transaction_count', 'created_by')
    list_filter = ('scope', 'is_active', 'branch')
    search_fields = ('name', 'description')
    autocomplete_fields = ('branch', 'created_by')
    ordering = ('name',)
    
    def transaction_count(self, obj):
        """Show number of transactions using this category"""
        from .models import Transaction
        count = Transaction.objects.filter(income_category=obj).count()
        if count > 0:
            return f"🔒 {count} transaction(s)"
        return "-"
    transaction_count.short_description = 'Transactions'
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent deletion of income categories used in transactions.
        """
        if obj:
            from .models import Transaction
            transaction_count = Transaction.objects.filter(income_category=obj).count()
            if transaction_count > 0:
                return False
        return super().has_delete_permission(request, obj)
    
    def get_actions(self, request):
        """
        Remove bulk delete for categories with transactions.
        """
        actions = super().get_actions(request)
        # Keep the delete action but it will be filtered by has_delete_permission
        return actions


@admin.register(ExpenditureCategory)
class ExpenditureCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'scope', 'branch', 'is_active', 'transaction_count', 'created_by')
    list_filter = ('scope', 'is_active', 'branch')
    search_fields = ('name', 'description')
    autocomplete_fields = ('branch', 'created_by')
    ordering = ('name',)
    
    def transaction_count(self, obj):
        """Show number of transactions using this category"""
        from .models import Transaction
        count = Transaction.objects.filter(expenditure_category=obj).count()
        if count > 0:
            return f"🔒 {count} transaction(s)"
        return "-"
    transaction_count.short_description = 'Transactions'
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent deletion of expenditure categories used in transactions.
        """
        if obj:
            from .models import Transaction
            transaction_count = Transaction.objects.filter(expenditure_category=obj).count()
            if transaction_count > 0:
                return False
        return super().has_delete_permission(request, obj)
    
    def get_actions(self, request):
        """
        Remove bulk delete for categories with transactions.
        """
        actions = super().get_actions(request)
        # Keep the delete action but it will be filtered by has_delete_permission
        return actions


@admin.register(FundAllocation)
class FundAllocationAdmin(admin.ModelAdmin):
    list_display = ('from_branch', 'to_branch', 'amount', 'allocated_by', 'allocated_date', 'is_active')
    list_filter = ('is_active', 'from_branch', 'to_branch', 'allocated_date')
    search_fields = ('description',)
    autocomplete_fields = ('from_branch', 'to_branch', 'allocated_by')
    date_hierarchy = 'allocated_date'
    ordering = ('-allocated_date',)
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent deletion of fund allocations through Django admin.
        This preserves audit trail and financial integrity.
        """
        return False
    
    def get_actions(self, request):
        """
        Remove the bulk delete action from the admin.
        """
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('branch', 'transaction_type', 'amount', 'date', 'is_fund_allocation', 'created_by', 'created_date')
    list_filter = ('transaction_type', 'branch', 'date')
    search_fields = ('description',)
    autocomplete_fields = ('branch', 'income_category', 'expenditure_category', 'fund_allocation', 'created_by')
    date_hierarchy = 'date'
    ordering = ('-date', '-created_date')
    
    def is_fund_allocation(self, obj):
        """Show if transaction is linked to a fund allocation"""
        if obj.fund_allocation:
            return "🔒 Protected"
        return "-"
    is_fund_allocation.short_description = 'Fund Allocation'
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent deletion of transactions linked to fund allocations.
        """
        if obj and obj.fund_allocation:
            return False
        return super().has_delete_permission(request, obj)
    
    def has_change_permission(self, request, obj=None):
        """
        Prevent editing of transactions linked to fund allocations.
        """
        if obj and obj.fund_allocation:
            return False
        return super().has_change_permission(request, obj)
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make all fields readonly for fund allocation transactions.
        """
        if obj and obj.fund_allocation:
            return [f.name for f in self.model._meta.fields]
        return super().get_readonly_fields(request, obj)