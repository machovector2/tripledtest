from django.urls import path
from . import views


from django.conf import settings
from django.conf.urls.static import static

from django.views.generic import RedirectView


urlpatterns = [
    # Root URL - redirect to signin
    path('', RedirectView.as_view(url='/user/signin/', permanent=False), name='home'),
    
    # ======================ADMIN URLS=================================
    # Fix the /user redirect issue permanently
    path('user', RedirectView.as_view(url='/user/', permanent=True)),
    
    path('user/', views.userhome, name='user'),
    path('user/signin/', views.signin, name='signin'),

    path('user/signout/', views.signout, name='signout'),
    path('user/profile/', views.profile, name='profile'),
    path('user/create_realtor/', views.create_realtor, name='create_realtor'),
    path('user/realtor_detail/<int:id>', views.realtor_detail, name='realtor_detail'),
    path('user/edit_realtor/<int:id>', views.edit_realtor, name='edit_realtor'),
    path('user/realtors_page', views.realtors_page, name='realtors_page'),
    path('user/delete-realtor/<int:id>/', views.delete_realtor, name='delete_realtor'),
    
    
    # Password reset URLs
    path('password-reset/', views.password_reset_request, name='password_reset'),
    path('password-reset/done/', views.password_reset_done, name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset-complete/', views.password_reset_complete, name='password_reset_complete'),
     
    
    
    path('user/pay-all-commissions/<int:realtor_id>/', views.pay_all_commissions, name='pay_all_commissions'),
    path('pay-commission/<int:commission_id>/', views.pay_commission, name='pay_commission'),
    
    
    # Property URLs
    path('user/properties/', views.property_list, name='property_list'),
    path('user/properties/register/', views.register_property, name='register_property'),
    path('user/properties/<int:property_id>/', views.property_detail, name='property_detail'),
    path('user/property/edit/<int:property_id>/', views.edit_property, name='edit_property'),
    path('user/property/<int:property_id>/delete/', views.delete_property, name='delete_property'),
    
    # commission URLs
    path('user/commissions/', views.commissions_list, name='commissions_list'),
    
    path('commissions/unpaid/print/', views.unpaid_commissions_print, name='unpaid_commissions_print'),
    path('realtor/<int:realtor_id>/unpaid-commissions-print/', views.realtor_unpaid_commissions_print, name='realtor_unpaid_commissions_print'),
    # Your other URLs...



    # Property Sales URLs
    path('user/property-sales/', views.property_sales_list, name='property_sales_list'),
    path('user/property-sales/register/', views.register_property_sale, name='register_property_sale'),
    path('user/property-sales/<int:id>/', views.property_sale_detail, name='property_sale_detail'),
    path('user/property-sale/<int:sale_id>/invoice/', views.property_sale_invoice, name='property_sale_invoice'),
#     property sale email
    path('send-client-email/<int:sale_id>/', views.send_client_email, name='send_client_email'),
    
    path('property-sale/<int:sale_id>/send-email/', views.send_private_email, name='send_private_email'),
    
    path('bulk-email/', views.bulk_email, name='bulk_email'),
    path('send-bulk-email/', views.send_bulk_email, name='send_bulk_email'),
    
    # Bulk email to realtors
    path('bulk-email-realtors/', views.bulk_email_realtors, name='bulk_email_realtors'),
    path('send-bulk-email-realtors/', views.send_bulk_email_realtors, name='send_bulk_email_realtors'),

    
    
    # Frontend Extras URLs
    path('user/frontend-extras/', views.frontend_extras, name='frontend_extras'),
    
    
    # general settings: 
    path('user/settings/general/', views.general_settings, name='general_settings'),
    
    
    
    
    
     # Status management URLs
    path('realtor/<int:realtor_id>/toggle-status/', 
         views.toggle_realtor_status, 
         name='toggle_realtor_status'),
    
    path('realtor/bulk-update-status/', 
         views.bulk_update_realtor_status, 
         name='bulk_update_realtor_status'),
    
    # API endpoint for AJAX operations (optional)
    path('api/realtor/<int:realtor_id>/status/', 
         views.realtor_status_api, 
         name='realtor_status_api'),
    
    
    
    
     #     refferal
    path('realtor/register/', views.realtor_register, name='realtor_register'),
    path('realtor/register/<str:referral_code>/', views.realtor_register, name='realtor_register_with_referral'),
    

     # toggle developement status 
    path('user/property-sale/<int:sale_id>/mark-developed/', views.mark_property_developed, name='mark_property_developed'),
     
     
     # Secretary Admin URLs
    path('secretary-admins/', views.secretary_list, name='secretary_list'),
    path('secretary-admins/create/', views.create_secretary, name='create_secretary'),
    path('secretary-admins/edit/<int:secretary_id>/', views.edit_secretary, name='edit_secretary'),
    path('secretary-admins/delete/<int:secretary_id>/', views.delete_secretary, name='delete_secretary'),
    path('secretary-admins/toggle-status/<int:secretary_id>/', views.toggle_secretary_status, name='toggle_secretary_status'),
    path('secretary-admins/reset-password/<int:secretary_id>/', views.reset_secretary_password, name='reset_secretary_password'),
    path('secretary-dashboard/', views.secretary_dashboard, name='secretary_dashboard'),
    
]
