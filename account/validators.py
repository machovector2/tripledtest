from django.core.exceptions import ValidationError

def validate_minimum_length(value):
    """Custom password validator that only requires minimum 4 characters"""
    if len(value) < 4:
        raise ValidationError(
            'Password must be at least 4 characters long.',
            code='password_too_short',
        )
