import { Pipe, PipeTransform } from '@angular/core';
import { LanguageService } from '../services/language.service';


@Pipe({ name: 't', standalone: true, pure: false })
export class TPipe implements PipeTransform {
  constructor(private lang: LanguageService) {}
  transform(key: string): string {
    return this.lang.t(key);
  }
}
