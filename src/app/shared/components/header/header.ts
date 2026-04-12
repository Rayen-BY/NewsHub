import { DOCUMENT } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './header.html',
  styleUrl: './header.css'
})
export class HeaderComponent implements OnInit {
  private readonly document = inject(DOCUMENT);
  private readonly storageKey = 'f-news-theme';

  isDarkMode = false;

  ngOnInit(): void {
    const storedTheme = localStorage.getItem(this.storageKey);
    const resolvedTheme = storedTheme === 'dark' ? 'dark' : 'light';

    this.isDarkMode = resolvedTheme === 'dark';
    this.applyTheme();

    if (!storedTheme) {
      localStorage.setItem(this.storageKey, resolvedTheme);
    }
  }

  toggleTheme(): void {
    this.isDarkMode = !this.isDarkMode;
    this.applyTheme();
    localStorage.setItem(this.storageKey, this.isDarkMode ? 'dark' : 'light');
  }

  private applyTheme(): void {
    this.document.documentElement.setAttribute('data-theme', this.isDarkMode ? 'dark' : 'light');
  }
}