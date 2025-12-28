from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from .models import *
from .validators import validate_minimum_length
from django.db.models import Sum, Q


class NoErrorTextInput(forms.TextInput):
    """Custom widget that doesn't display field errors"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'class': 'form-control'})

    def render(self, name, value, attrs=None, renderer=None):
        # Override to prevent error display
        return super().render(name, value, attrs, renderer)


class NoErrorPasswordInput(forms.PasswordInput):
    """Custom widget that doesn't display field errors"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'class': 'form-control'})

    def render(self, name, value, attrs=None, renderer=None):
        # Override to prevent error display
        return super().render(name, value, attrs, renderer)


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        max_length=254,
        widget=NoErrorTextInput(attrs={
            'placeholder': 'Username or email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=NoErrorPasswordInput(attrs={
            'placeholder': 'Password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'location', 'state', 'address', 'branch_type', 'allocated_funds']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'required': True}),
            'branch_type': forms.Select(attrs={'class': 'form-control', 'required': True}),
            'allocated_funds': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'value': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default value for allocated_funds if not provided
        if not self.instance.pk and 'allocated_funds' not in self.data:
            self.fields['allocated_funds'].initial = 0

class BranchAdminForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_first_name'}))
    last_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_last_name'}))
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_username', 'placeholder': 'Will be generated from first and last name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'minlength': '4'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'minlength': '4'}))

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields didn't match.")
        return password2

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        if password1 and len(password1) < 4:
            raise forms.ValidationError("Password must be at least 4 characters long.")
        return password1

    def save(self):
        # Create user manually without Django's complex validation
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone=self.cleaned_data.get('phone', ''),
            user_type='branch_admin'
        )
        return user

class BranchAdminAssignmentForm(forms.Form):
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True
    )
    admins = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(user_type='branch_admin'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False
    )

class FundAllocationForm(forms.ModelForm):
    class Meta:
        model = FundAllocation
        fields = ['to_branch', 'amount', 'description']
        widgets = {
            'to_branch': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Store user for use in clean method
        self.user = user

        if user and user.user_type in ['admin', 'chief_accountant']:
            # Only show sub branches for allocation
            self.fields['to_branch'].queryset = Branch.objects.filter(
                is_active=True,
                branch_type='sub'
            )
    
    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        to_branch = cleaned_data.get('to_branch')
        
        if amount and self.user:
            # Get the main branch (Enugu)
            try:
                main_branch = Branch.objects.get(branch_type='main', is_active=True)
                main_balance = main_branch.get_balance()
                
                # Check if main branch has sufficient balance
                if amount > main_balance:
                    from django.core.exceptions import ValidationError
                    raise ValidationError(
                        f"❌ Insufficient Funds in Main Branch!\n\n"
                        f"Cannot allocate ₦{amount:,.2f} because the main branch only has ₦{main_balance:,.2f} available.\n\n"
                        f"Available Balance: ₦{main_balance:,.2f}\n"
                        f"Requested Amount: ₦{amount:,.2f}\n"
                        f"Shortfall: ₦{(amount - main_balance):,.2f}\n\n"
                        f"Please reduce the allocation amount or add more funds to the main branch first."
                    )
            except Branch.DoesNotExist:
                from django.core.exceptions import ValidationError
                raise ValidationError("Main branch not found. Please contact system administrator.")
        
        return cleaned_data

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['transaction_type', 'amount', 'description', 'date', 'income_category', 'expenditure_category']
        widgets = {
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'income_category': forms.Select(attrs={'class': 'form-control'}),
            'expenditure_category': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        transaction_type = kwargs.pop('transaction_type', None)
        
        # If transaction_type is predetermined and form is being bound (POST data exists),
        # ensure transaction_type is in the data before form initialization
        if transaction_type and args and len(args) > 0:
            from django.http import QueryDict
            data = args[0]
            if isinstance(data, QueryDict):
                mutable_data = data.copy()
                mutable_data['transaction_type'] = transaction_type
                args = (mutable_data,) + args[1:]
        
        super().__init__(*args, **kwargs)
        
        # Store user for use in clean method
        self.user = user

        # If transaction_type is predetermined, hide the field and set it
        if transaction_type:
            self._predetermined_transaction_type = transaction_type
            self.fields['transaction_type'].widget = forms.HiddenInput()
            self.fields['transaction_type'].initial = transaction_type

        if user:
            if user.user_type in ['admin', 'chief_accountant']:
                self.fields['branch'] = forms.ModelChoiceField(
                    queryset=Branch.objects.filter(is_active=True),
                    widget=forms.Select(attrs={'class': 'form-control'}),
                    required=True
                )
                # Super admin can see all categories
                income_categories = IncomeCategory.objects.filter(is_active=True)
                expenditure_categories = ExpenditureCategory.objects.filter(is_active=True)
            else:
                # Branch admin - can add income AND expenditure to their branch
                branch = user.managed_branch
                if branch:
                    # Branch admins can add both income and expenditure
                    # Filter income categories by scope (sub branches + all, exclude main-only)
                    income_categories = IncomeCategory.objects.filter(
                        Q(scope__in=['all', 'sub']) | Q(branch=branch),
                        is_active=True
                    )
                    
                    # Filter expenditure categories by scope
                    expenditure_categories = ExpenditureCategory.objects.filter(
                        Q(scope__in=['all', 'sub']) | Q(branch=branch),
                        is_active=True
                    )
                else:
                    income_categories = IncomeCategory.objects.none()
                    expenditure_categories = ExpenditureCategory.objects.none()

            self.fields['income_category'].queryset = income_categories
            self.fields['expenditure_category'].queryset = expenditure_categories

    def clean(self):
        cleaned_data = super().clean()
        user = getattr(self, 'user', None)
        
        # If transaction_type was predetermined, ensure it's in cleaned_data
        if hasattr(self, '_predetermined_transaction_type'):
            cleaned_data['transaction_type'] = self._predetermined_transaction_type
        
        # Branch admins can now add both income and expenditure
        # No restriction needed here - scope filtering handles security
        
        # Add balance validation for expenditure transactions
        # PREVENT NEGATIVE BALANCES - No expenditure should exceed available balance
        transaction_type = cleaned_data.get('transaction_type')
        amount = cleaned_data.get('amount')
        
        if transaction_type == 'expenditure' and amount:
            # Get the branch for balance calculation
            if user and user.user_type in ['admin', 'chief_accountant']:
                branch = cleaned_data.get('branch')
            else:
                branch = user.managed_branch if user else None
            
            if branch:
                current_balance = branch.get_balance()
                
                # Prevent negative balances - expenditure cannot exceed current balance
                if amount > current_balance:
                    raise forms.ValidationError(
                        f"❌ Insufficient Funds in {branch.name}!\n\n"
                        f"Cannot record expenditure of ₦{amount:,.2f} because the branch only has ₦{current_balance:,.2f} available.\n\n"
                        f"Available Balance: ₦{current_balance:,.2f}\n"
                        f"Requested Expenditure: ₦{amount:,.2f}\n"
                        f"Shortfall: ₦{(amount - current_balance):,.2f}\n\n"
                        f"This system does NOT allow negative balances. Please ensure sufficient funds are available before recording expenditures."
                    )
        
        return cleaned_data

class IncomeCategoryForm(forms.ModelForm):
    class Meta:
        model = IncomeCategory
        fields = ['name', 'description', 'scope']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'scope': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.user_type in ['admin', 'chief_accountant']:
            self.fields['branch'] = forms.ModelChoiceField(
                queryset=Branch.objects.filter(is_active=True),
                widget=forms.Select(attrs={'class': 'form-control'}),
                required=False,
                help_text='Leave empty for global categories'
            )

class ExpenditureCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenditureCategory
        fields = ['name', 'description', 'scope']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'scope': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.user_type in ['admin', 'chief_accountant']:
            self.fields['branch'] = forms.ModelChoiceField(
                queryset=Branch.objects.filter(is_active=True),
                widget=forms.Select(attrs={'class': 'form-control'}),
                required=False,
                help_text='Leave empty for global categories'
            )
