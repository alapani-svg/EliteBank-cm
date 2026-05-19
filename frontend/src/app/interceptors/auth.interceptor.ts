import { HttpInterceptorFn, HttpRequest, HttpHandlerFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

// Auth endpoints that must NOT receive a Bearer token (would cause loops)
const AUTH_ENDPOINTS = ['/api/auth/login/', '/api/auth/register/', '/api/auth/token/refresh/'];

export const authInterceptor: HttpInterceptorFn = (req: HttpRequest<unknown>, next: HttpHandlerFn) => {
  const auth  = inject(AuthService);
  const token = auth.getAccessToken();

  const isAuthRoute = AUTH_ENDPOINTS.some(e => req.url.includes(e));

  // Skip public auth endpoints
  if (isAuthRoute || !token) return next(req);

  // Attach Bearer token
  const authReq = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401) {
        // Try silent refresh
        return auth.refreshAccessToken().pipe(
          switchMap(({ access }) =>
            next(req.clone({ setHeaders: { Authorization: `Bearer ${access}` } }))
          ),
          catchError(refreshErr => {
            auth.logout();
            return throwError(() => refreshErr);
          })
        );
      }
      return throwError(() => err);
    })
  );
};
