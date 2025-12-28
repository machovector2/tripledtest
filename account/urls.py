# urls.py
from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Branch Management
    path('create-branch/', views.create_branch, name='create_branch'),
    path('manage-branches/', views.manage_branches, name='manage_branches'),
    path('assign-branch-admin/', views.assign_branch_admin, name='assign_branch_admin'),
    path('assign-branch-admin/<int:branch_id>/', views.assign_branch_admin, name='assign_branch_admin_with_branch'),
    path('assign-branch-admin/user/<int:user_id>/', views.assign_branch_admin, name='assign_branch_admin_with_user'),
    path('delete-branch/<int:branch_id>/', views.delete_branch, name='delete_branch'),

    # User Management
    path('create-branch-admin/', views.create_branch_admin, name='create_branch_admin'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('toggle-user-status/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('reset-password/<int:user_id>/', views.reset_user_password, name='reset_user_password'),

    # Fund Management
    path('allocate-funds/', views.allocate_funds, name='allocate_funds'),
    path('allocate-funds/<int:branch_id>/', views.allocate_funds, name='allocate_funds_with_branch'),
    path('fund-allocations/', views.fund_allocations, name='fund_allocations'),
    path('reverse-allocation/<int:allocation_id>/', views.reverse_fund_allocation, name='reverse_fund_allocation'),
    path('delete-allocation/<int:allocation_id>/', views.delete_fund_allocation, name='delete_fund_allocation'),

    # Transactions
    path('transactions/', views.transactions, name='transactions'),
    path('add-transaction/', views.add_transaction, name='add_transaction'),
    path('add-income/', views.add_income, name='add_income'),
    path('add-expenditure/', views.add_expenditure, name='add_expenditure'),
    path('edit-transaction/<int:transaction_id>/', views.edit_transaction, name='edit_transaction'),
    path('delete-transaction/<int:transaction_id>/', views.delete_transaction, name='delete_transaction'),

    # Categories
    path('manage-categories/', views.manage_categories, name='manage_categories'),
    path('add-income-category/', views.add_income_category, name='add_income_category'),
    path('add-expenditure-category/', views.add_expenditure_category, name='add_expenditure_category'),
    path('edit-income-category/<int:category_id>/', views.edit_income_category, name='edit_income_category'),
    path('edit-expenditure-category/<int:category_id>/', views.edit_expenditure_category, name='edit_expenditure_category'),
    path('delete-income-category/<int:category_id>/', views.delete_income_category, name='delete_income_category'),
    path('delete-expenditure-category/<int:category_id>/', views.delete_expenditure_category, name='delete_expenditure_category'),
    
    # Reports
    path('reports/', views.reports, name='reports'),
    
    # Commissions
    path('commissions/', views.commissions_list, name='account_commissions_list'),
    path('commissions/pay/<int:commission_id>/', views.pay_commission, name='account_pay_commission'),
]
