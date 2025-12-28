from django.urls import path
from . import views


from django.conf import settings
from django.conf.urls.static import static

from django.views.generic import RedirectView


urlpatterns = [
    # Root URL - placeholder for future frontend website
    # For now, redirect to admin portal signin
    path('', RedirectView.as_view(url='/admin-portal/signin/', permanent=False), name='home'),
    
    # ======================ADMIN PORTAL URLS=================================
    # Admin/Realtor Dashboard (previously /user/)
    path('admin-portal/', views.userhome, name='user'),
    path('admin-portal/signin/', views.signin, name='signin'),
    path('admin-portal/signout/', views.signout, name='signout'),
    path('admin-portal/profile/', views.profile, name='profile'),
    
    # Realtor Management
    path('admin-portal/create_realtor/', views.create_realtor, name='create_realtor'),
    path('admin-portal/realtor_detail/<int:id>', views.realtor_detail, name='realtor_detail'),
    path('admin-portal/edit_realtor/<int:id>', views.edit_realtor, name='edit_realtor'),
    path('admin-portal/realtors_page', views.realtors_page, name='realtors_page'),
    path('admin-portal/delete-realtor/<int:id>/', views.delete_realtor, name='delete_realtor'),
    
    # Password reset URLs
    path('password-reset/', views.password_reset_request, name='password_reset'),
    path('password-reset/done/', views.password_reset_done, name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset-complete/', views.password_reset_complete, name='password_reset_complete'),
     
    # Commission Payment
    path('admin-portal/pay-all-commissions/<int:realtor_id>/', views.pay_all_commissions, name='pay_all_commissions'),
    path('pay-commission/<int:commission_id>/', views.pay_commission, name='pay_commission'),
    
    # Property URLs
    path('admin-portal/properties/', views.property_list, name='property_list'),
    path('admin-portal/properties/register/', views.register_property, name='register_property'),
    path('admin-portal/properties/<int:property_id>/', views.property_detail, name='property_detail'),
    path('admin-portal/property/edit/<int:property_id>/', views.edit_property, name='edit_property'),
    path('admin-portal/property/<int:property_id>/delete/', views.delete_property, name='delete_property'),
    path('api/plots/get/', views.ajax_get_plots, name='ajax_get_plots'),
    path('api/plots/toggle/', views.ajax_toggle_plot_status, name='ajax_toggle_plot_status'),
    
    # Commission URLs
    path('admin-portal/commissions/', views.commissions_list, name='commissions_list'),
    path('commissions/unpaid/print/', views.unpaid_commissions_print, name='unpaid_commissions_print'),
    path('realtor/<int:realtor_id>/unpaid-commissions-print/', views.realtor_unpaid_commissions_print, name='realtor_unpaid_commissions_print'),

    # Property Sales URLs
    path('admin-portal/property-sales/', views.property_sales_list, name='property_sales_list'),
    path('admin-portal/property-sales/register/', views.register_property_sale, name='register_property_sale'),
    path('admin-portal/property-sales/<int:id>/', views.property_sale_detail, name='property_sale_detail'),
    path('admin-portal/property-sale/<int:sale_id>/invoice/', views.property_sale_invoice, name='property_sale_invoice'),
    
    # Property sale emails
    path('send-client-email/<int:sale_id>/', views.send_client_email, name='send_client_email'),
    path('property-sale/<int:sale_id>/send-email/', views.send_private_email, name='send_private_email'),
    
    # Bulk emails
    path('bulk-email/', views.bulk_email, name='bulk_email'),
    path('send-bulk-email/', views.send_bulk_email, name='send_bulk_email'),
    path('bulk-email-realtors/', views.bulk_email_realtors, name='bulk_email_realtors'),
    path('send-bulk-email-realtors/', views.send_bulk_email_realtors, name='send_bulk_email_realtors'),

    # Frontend Extras URLs
    path('admin-portal/frontend-extras/', views.frontend_extras, name='frontend_extras'),
    
    # General settings
    path('admin-portal/settings/general/', views.general_settings, name='general_settings'),

    # Realtor Status management URLs
    path('realtor/<int:realtor_id>/toggle-status/', 
         views.toggle_realtor_status, 
         name='toggle_realtor_status'),
    
    path('realtor/bulk-update-status/', 
         views.bulk_update_realtor_status, 
         name='bulk_update_realtor_status'),
    
    # API endpoint for AJAX operations
    path('api/realtor/<int:realtor_id>/status/', 
         views.realtor_status_api, 
         name='realtor_status_api'),
    
    # Public Realtor Registration (Estate)
    path('realtor/register/', views.realtor_register, name='realtor_register'),
    path('realtor/register/<str:referral_code>/', views.realtor_register, name='realtor_register_with_referral'),

    # Property development status toggle
    path('admin-portal/property-sale/<int:sale_id>/mark-developed/', views.mark_property_developed, name='mark_property_developed'),
     
    # Secretary Admin URLs
    path('secretary-admins/', views.secretary_list, name='secretary_list'),
    path('secretary-admins/create/', views.create_secretary, name='create_secretary'),
    path('secretary-admins/edit/<int:secretary_id>/', views.edit_secretary, name='edit_secretary'),
    path('secretary-admins/delete/<int:secretary_id>/', views.delete_secretary, name='delete_secretary'),
    path('secretary-admins/toggle-status/<int:secretary_id>/', views.toggle_secretary_status, name='toggle_secretary_status'),
    path('secretary-admins/reset-password/<int:secretary_id>/', views.reset_secretary_password, name='reset_secretary_password'),
    path('secretary-dashboard/', views.secretary_dashboard, name='secretary_dashboard'),

    # Chief Accountant URLs
    path('chief-accountants/', views.chief_accountant_list, name='chief_accountant_list'),
    path('chief-accountants/create/', views.create_chief_accountant, name='create_chief_accountant'),
    path('chief-accountants/edit/<int:user_id>/', views.edit_chief_accountant, name='edit_chief_accountant'),
    path('chief-accountants/delete/<int:user_id>/', views.delete_chief_accountant, name='delete_chief_accountant'),
    path('chief-accountants/toggle-status/<int:user_id>/', views.toggle_chief_accountant_status, name='toggle_chief_accountant_status'),
    path('chief-accountants/reset-password/<int:user_id>/', views.reset_chief_accountant_password, name='reset_chief_accountant_password'),
    
]
