export interface User {
  id: string;
  full_name: string;
  email: string;
  phone_number: string;
  avatar_url: string;
  language: string;
  balance_xaf: number;
  is_verified: boolean;
  is_active: boolean;
  two_factor_enabled: boolean;
  email_notifications: boolean;
  sms_alerts: boolean;
  date_joined: string;
  updated_at: string;
  password_changed_at: string | null;
}

export interface ProfileUpdatePayload {
  full_name?: string;
  phone_number?: string;
  language?: string;
  email_notifications?: boolean;
  sms_alerts?: boolean;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
  confirm_password: string;
}
