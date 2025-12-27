from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

# Import User from tripled app to avoid model conflicts
from tripled.models import User

class Branch(models.Model):
    BRANCH_TYPES = (
        ('main', 'Main Branch'),
        ('sub', 'Sub Branch'),
    )

    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    address = models.TextField()
    branch_type = models.CharField(max_length=10, choices=BRANCH_TYPES, default='sub')
    created_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    allocated_funds = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_branches', null=True, blank=True)

    # Multiple admins can be assigned to a branch
    admins = models.ManyToManyField(User, related_name='managed_branches', blank=True)

    def __str__(self):
        return f"{self.name} - {self.location}"

    def get_total_income(self):
        return self.transactions.filter(transaction_type='income').aggregate(
            models.Sum('amount'))['amount__sum'] or Decimal('0')

    def get_total_expenditure(self):
        return self.transactions.filter(transaction_type='expenditure').aggregate(
            models.Sum('amount'))['amount__sum'] or Decimal('0')

    def get_balance(self):
        return self.get_total_income() - self.get_total_expenditure()

    def get_remaining_allocated_funds(self):
        return self.allocated_funds - self.get_total_expenditure()

    @property
    def is_main_branch(self):
        return self.branch_type == 'main'

class IncomeCategory(models.Model):
    CATEGORY_SCOPES = (
        ('main', 'Main Branch Only'),
        ('sub', 'Sub Branches Only'),
        ('all', 'All Branches'),
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    scope = models.CharField(max_length=10, choices=CATEGORY_SCOPES, default='all')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.get_scope_display()})"

class ExpenditureCategory(models.Model):
    CATEGORY_SCOPES = (
        ('main', 'Main Branch Only'),
        ('sub', 'Sub Branches Only'),
        ('all', 'All Branches'),
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    scope = models.CharField(max_length=10, choices=CATEGORY_SCOPES, default='all')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.get_scope_display()})"

class FundAllocation(models.Model):
    """
    Track fund allocations from main branch to sub branches.
    
    IMPORTANT: Fund allocations CANNOT be deleted (PROTECT constraint).
    This preserves financial integrity and audit trail.
    To correct errors, use the reversal feature instead.
    """
    from_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='fund_allocations_made')
    to_branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='fund_allocations_received')
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    description = models.TextField()
    allocated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    allocated_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"₦{self.amount} from {self.from_branch.name} to {self.to_branch.name}"
    
    def delete(self, *args, **kwargs):
        """
        Override delete to prevent direct deletion of fund allocations.
        This is a safety measure to preserve audit trail.
        """
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied(
            "Fund allocations cannot be deleted for audit compliance. "
            "Use the reversal feature instead to maintain complete transaction history."
        )

    class Meta:
        ordering = ['-allocated_date']

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('income', 'Income'),
        ('expenditure', 'Expenditure'),
    )

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    description = models.TextField()
    date = models.DateField()
    income_category = models.ForeignKey(IncomeCategory, on_delete=models.CASCADE, null=True, blank=True)
    expenditure_category = models.ForeignKey(ExpenditureCategory, on_delete=models.CASCADE, null=True, blank=True)
    fund_allocation = models.ForeignKey(FundAllocation, on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_date = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Strict balance validation - no expenditures allowed on negative balance
        if self.transaction_type == 'expenditure' and self.branch_id:
            current_balance = self.branch.get_balance()
            if current_balance < self.amount:
                if self.fund_allocation_id:
                    raise ValidationError(
                        f"Cannot allocate funds. Main branch has insufficient balance of ₦{current_balance:,.2f}. "
                        f"Trying to allocate ₦{self.amount:,.2f}. "
                        f"Please add income to the main branch first to increase the balance."
                    )
                else:
                    raise ValidationError(
                        f"Insufficient funds. Current balance is ₦{current_balance:,.2f}, "
                        f"but you're trying to spend ₦{self.amount:,.2f}. "
                        f"Available balance: ₦{current_balance:,.2f}"
                    )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.branch.name} - {self.transaction_type} - ₦{self.amount}"

    class Meta:
        ordering = ['-date', '-created_date']
