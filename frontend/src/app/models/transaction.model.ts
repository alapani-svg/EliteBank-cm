export type TransactionType   = 'TRANSFER' | 'DEPOSIT' | 'WITHDRAWAL' | 'BILL_PAYMENT' | 'AIRTIME';
export type TransactionStatus = 'PENDING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface Transaction {
  id: string;
  reference: string;
  transaction_type: TransactionType;
  status: TransactionStatus;
  amount: number;
  currency: string;
  description: string;
  sender: string | null;
  sender_name: string | null;
  sender_email: string | null;
  recipient: string | null;
  recipient_name: string | null;
  recipient_email: string | null;
  payment_reference: string;
  payment_method: string;
  payment_phone: string;
  created_at: string;
  updated_at: string;
}

export interface TransferPayload {
  recipient_identifier: string;
  amount: number;
  description?: string;
}

export type PaymentMethod = 'orange' | 'mtn';

export interface DepositPayload {
  amount: number;
  phone: string;
  payment_method: PaymentMethod;
}

export interface DepositResponse {
  status: 'pending' | 'completed' | 'failed';
  reference: string;
  message: string;
  transaction: Transaction;
}

export type BillProvider = 'ENEO' | 'CAMWATER' | 'CANAL+' | 'CAMTEL';

export interface BillPaymentPayload {
  provider: BillProvider;
  meter_number: string;
  amount: number;
}

export interface AirtimePayload {
  network: 'mtn' | 'orange';
  phone: string;
  amount: number;
}

export interface WithdrawalPayload {
  amount: number;
  phone: string;
  payment_method: PaymentMethod;
}

export interface WithdrawalResponse {
  status: 'completed' | 'failed';
  reference: string;
  message: string;
  transaction: Transaction;
}

export type BeneficiaryCategory = 'TRANSFER' | 'AIRTIME' | 'BILL_PAYMENT';

export interface Beneficiary {
  id: string;
  name: string;
  identifier: string;
  category: BeneficiaryCategory;
  provider: string;
  created_at: string;
}

export interface BeneficiaryPayload {
  name: string;
  identifier: string;
  category: BeneficiaryCategory;
  provider?: string;
}

export type NotificationKind = 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';
export type NotificationCategory =
  | 'TRANSFER' | 'DEPOSIT' | 'WITHDRAWAL' | 'BILL_PAYMENT' | 'AIRTIME'
  | 'SECURITY' | 'ACCOUNT' | 'SYSTEM';

export interface AppNotification {
  id: string;
  kind: NotificationKind;
  category: NotificationCategory;
  title: string;
  body: string;
  action_url: string;
  read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  results: AppNotification[];
  unread_count: number;
  total: number;
}
