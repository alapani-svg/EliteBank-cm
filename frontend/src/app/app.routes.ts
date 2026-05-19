import { Routes } from '@angular/router';
import { Register } from './auth/register/register';
import { Login } from './auth/login/login';
import { authGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./pages/home/home').then(m => m.Home) },
  { path: 'register', component: Register },
  { path: 'login',    component: Login },
  {
    path: 'forgot-password',
    loadComponent: () => import('./auth/forgot-password/forgot-password').then(m => m.ForgotPassword),
  },
  {
    path: 'reset-password',
    loadComponent: () => import('./auth/reset-password/reset-password').then(m => m.ResetPassword),
  },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/dashboard/dashboard').then(m => m.Dashboard),
  },
  {
    path: 'profile',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/profile/profile').then(m => m.Profile),
  },
  {
    path: 'transactions',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/transactions/transactions').then(m => m.Transactions),
  },
  {
    path: 'transactions/transfer',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/transactions/transfer/transfer').then(m => m.Transfer),
  },
  {
    path: 'transactions/deposit',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/transactions/deposit/deposit').then(m => m.Deposit),
  },
  {
    path: 'transactions/withdrawal',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/transactions/withdrawal/withdrawal').then(m => m.Withdrawal),
  },
  {
    path: 'payments',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/payments/payments').then(m => m.Payments),
  },
  {
    path: 'notifications',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/notifications/notifications').then(m => m.Notifications),
  },
  { path: '**', redirectTo: 'login' },
];
