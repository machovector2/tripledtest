from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse

class AccountingSecurityMiddleware:
    """
    Restricts access to the Accounting application (/accounting/) 
    to authorized roles only.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Check if the path belongs to the accounting app
        # Most accounting URLs start with /accounting/ based on the project URL structure
        if request.path.startswith('/accounting/'):
            
            # CRITICAL SECURITY: Only Django superusers and chief accountants can access
            # the accounting dashboard. This blocks:
            # - Secretaries
            # - Branch admins (with LIMITED exceptions - see below)
            # - Regular realtor portal admins
            is_allowed = (
                request.user.is_superuser or 
                request.user.user_type == 'chief_accountant'
            )
            
            # BRANCH ADMIN LIMITED ACCESS:
            # Branch admins can ONLY access specific URLs for their branch operations
            if not is_allowed and request.user.user_type == 'branch_admin':
                # Define allowed URLs for branch admins
                BRANCH_ADMIN_ALLOWED_URLS = [
                    '/accounting/',
                    '/accounting/dashboard/',
                    '/accounting/add-income/',
                    '/accounting/transactions/',
                ]
                
                # Check if the current path is in the allowed list
                is_branch_admin_allowed = any(
                    request.path.startswith(url) or request.path == url.rstrip('/')
                    for url in BRANCH_ADMIN_ALLOWED_URLS
                )
                
                if is_branch_admin_allowed:
                    # Allow branch admin to access these specific URLs
                    return self.get_response(request)
                else:
                    # Block branch admin from other accounting URLs
                    messages.error(
                        request,
                        "Access Denied. Branch admins can only access their branch dashboard and add income transactions. "
                        "Other accounting features are restricted to Chief Accountants."
                    )
                    return redirect('accounting:dashboard')
            
            if not is_allowed:
                # Provide specific error messages based on user type
                user_type = getattr(request.user, 'user_type', 'unknown')
                
                if user_type == 'secretary':
                    messages.error(
                        request, 
                        "Access Denied. Secretaries are not authorized to access the Accounting system."
                    )
                    return redirect('secretary_dashboard')
                
                elif user_type == 'branch_admin':
                    # This shouldn't be reached due to the check above, but keep as fallback
                    messages.error(
                        request, 
                        "Access Denied. Branch admins have limited access to accounting features."
                    )
                    return redirect('accounting:dashboard')
                
                else:
                    # Regular admins or other user types
                    messages.error(
                        request, 
                        "Access Denied. Only Chief Accountants and System Administrators can access the Accounting system."
                    )
                    return redirect('user')

        return self.get_response(request)
