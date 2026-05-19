import { HttpInterceptorFn } from '@angular/common/http';
import { timeout, catchError } from 'rxjs/operators';
import { TimeoutError, throwError } from 'rxjs';

export const httpTimeoutInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req).pipe(
    timeout(1800),
    catchError(err => {
      if (err instanceof TimeoutError) {
        return throwError(() => ({
          error: { detail: 'Request timed out. Please check your connection and try again.' },
          status: 0,
        }));
      }
      return throwError(() => err);
    }),
  );
};
