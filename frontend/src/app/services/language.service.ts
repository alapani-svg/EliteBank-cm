import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { TRANSLATIONS, LangCode, SUPPORTED_LANGS } from '../i18n/translations';

const STORAGE_KEY = 'elite_lang';


@Injectable({ providedIn: 'root' })
export class LanguageService {

  private _current = new BehaviorSubject<LangCode>('en');
  currentLang$ = this._current.asObservable();
  get currentLang(): LangCode { return this._current.value; }

  readonly supported = SUPPORTED_LANGS;

  constructor() {
    const saved = (typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY)) as LangCode | null;
    if (saved && saved in TRANSLATIONS) {
      this._current.next(saved);
      this.applyHtmlLang(saved);
    } else {
      this.applyHtmlLang('en');
    }
  }

  /** Switch the UI language. Falls back to 'en' for unknown codes. */
  use(lang: string | null | undefined): void {
    const normalized = (lang === 'fr' ? 'fr' : 'en') as LangCode;
    if (normalized === this._current.value) return;
    this._current.next(normalized);
    try { localStorage.setItem(STORAGE_KEY, normalized); } catch {}
    this.applyHtmlLang(normalized);
  }

  /** Lookup a key. Falls back to en, then to the key itself. */
  t(key: string): string {
    const cur = this._current.value;
    return TRANSLATIONS[cur]?.[key]
        ?? TRANSLATIONS.en[key]
        ?? key;
  }

  private applyHtmlLang(lang: LangCode): void {
    if (typeof document !== 'undefined' && document.documentElement) {
      document.documentElement.lang = lang;
    }
  }
}
