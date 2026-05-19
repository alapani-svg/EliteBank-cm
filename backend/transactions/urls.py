from django.urls import path
from .views import (
    TransactionListView, TransactionDetailView, TransferView,
    DepositInitiateView, DepositStatusView, DepositCallbackView,
    BillPaymentView, AirtimeView, WithdrawalView, StatementView,
)

urlpatterns = [
    path('',                                TransactionListView.as_view(),   name='transaction-list'),
    path('<uuid:pk>/',                      TransactionDetailView.as_view(), name='transaction-detail'),
    path('transfer/',                       TransferView.as_view(),           name='transaction-transfer'),
    path('deposit/initiate/',               DepositInitiateView.as_view(),   name='deposit-initiate'),
    path('deposit/status/<str:reference>/', DepositStatusView.as_view(),     name='deposit-status'),
    path('deposit/callback/',               DepositCallbackView.as_view(),   name='deposit-callback'),
    path('bill-payment/',                   BillPaymentView.as_view(),       name='bill-payment'),
    path('airtime/',                        AirtimeView.as_view(),           name='airtime'),
    path('withdrawal/',                     WithdrawalView.as_view(),        name='withdrawal'),
    path('statement/',                      StatementView.as_view(),         name='statement'),
]
