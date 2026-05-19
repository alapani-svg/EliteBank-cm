import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { Beneficiary, BeneficiaryPayload, BeneficiaryCategory } from '../models/transaction.model';

@Injectable({ providedIn: 'root' })
export class BeneficiaryService {

  private api = environment.apiUrl;

  constructor(private http: HttpClient) {}

  list(category?: BeneficiaryCategory): Observable<Beneficiary[]> {
    let params = new HttpParams();
    if (category) params = params.set('category', category);
    return this.http.get<Beneficiary[]>(`${this.api}/api/auth/beneficiaries/`, { params });
  }

  create(payload: BeneficiaryPayload): Observable<Beneficiary> {
    return this.http.post<Beneficiary>(`${this.api}/api/auth/beneficiaries/`, payload);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.api}/api/auth/beneficiaries/${id}/`);
  }
}
