import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  Transaction, TransferPayload, DepositPayload, DepositResponse,
  BillPaymentPayload, AirtimePayload, WithdrawalPayload, WithdrawalResponse,
} from '../models/transaction.model';

@Injectable({ providedIn: 'root' })
export class TransactionService {

  private api = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getAll(filters?: { type?: string; status?: string }): Observable<Transaction[]> {
    let params = new HttpParams();
    if (filters?.type)   params = params.set('type',   filters.type);
    if (filters?.status) params = params.set('status', filters.status);
    return this.http.get<Transaction[]>(`${this.api}/api/transactions/`, { params });
  }

  getById(id: string): Observable<Transaction> {
    return this.http.get<Transaction>(`${this.api}/api/transactions/${id}/`);
  }

  transfer(payload: TransferPayload): Observable<Transaction> {
    return this.http.post<Transaction>(`${this.api}/api/transactions/transfer/`, payload);
  }

  initiateDeposit(payload: DepositPayload): Observable<DepositResponse> {
    return this.http.post<DepositResponse>(`${this.api}/api/transactions/deposit/initiate/`, payload);
  }

  checkDepositStatus(reference: string): Observable<DepositResponse> {
    return this.http.get<DepositResponse>(`${this.api}/api/transactions/deposit/status/${reference}/`);
  }

  payBill(payload: BillPaymentPayload): Observable<Transaction> {
    return this.http.post<Transaction>(`${this.api}/api/transactions/bill-payment/`, payload);
  }

  purchaseAirtime(payload: AirtimePayload): Observable<Transaction> {
    return this.http.post<Transaction>(`${this.api}/api/transactions/airtime/`, payload);
  }

  withdraw(payload: WithdrawalPayload): Observable<WithdrawalResponse> {
    return this.http.post<WithdrawalResponse>(`${this.api}/api/transactions/withdrawal/`, payload);
  }

  downloadStatement(dateFrom: string, dateTo: string, format: 'pdf' | 'csv'): Observable<Blob> {
    const params = new HttpParams()
      .set('from', dateFrom)
      .set('to',   dateTo)
      .set('fmt',  format);
    return this.http.get(`${this.api}/api/transactions/statement/`, {
      params, responseType: 'blob',
    });
  }
}
