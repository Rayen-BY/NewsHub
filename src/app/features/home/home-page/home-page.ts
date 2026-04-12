import { CommonModule } from '@angular/common';
import { Component, OnInit, inject } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { CATEGORY_OPTIONS } from '../../../core/models/category.model';
import {
  COUNTRY_OPTIONS,
  DATA_TYPE_OPTIONS,
  DEFAULT_NEWS_FILTERS,
  NewsFilters,
  SOURCE_OPTIONS
} from '../../../core/models/filter.model';
import { NewsArticle } from '../../../core/models/news.model';
import { NewsService } from '../../../core/services/news';
import { HeaderComponent } from '../../../shared/components/header/header';
import { HeroBannerComponent } from '../../../shared/components/hero-banner/hero-banner';
import { CategoryFilterComponent } from '../../../shared/components/category-filter/category-filter';
import { NewsCardComponent } from '../../../shared/components/news-card/news-card';
import { FooterComponent } from '../../../shared/components/footer/footer';

@Component({
  selector: 'app-home-page',
  standalone: true,
  imports: [
    CommonModule,
    HeaderComponent,
    HeroBannerComponent,
    CategoryFilterComponent,
    NewsCardComponent,
    FooterComponent
  ],
  templateUrl: './home-page.html',
  styleUrl: './home-page.css'
})
export class HomePageComponent implements OnInit {
  private readonly newsService = inject(NewsService);
  private readonly rateLimitWindowMs = 15 * 60 * 1000;
  private rateLimitedUntil = 0;
  private pendingLoadId: ReturnType<typeof setTimeout> | null = null;

  readonly categories = CATEGORY_OPTIONS;
  readonly countryOptions = COUNTRY_OPTIONS;
  readonly sourceOptions = SOURCE_OPTIONS;
  readonly dataTypeOptions = DATA_TYPE_OPTIONS;

  filters: NewsFilters = { ...DEFAULT_NEWS_FILTERS };
  visibleArticles: NewsArticle[] = [];
  loading = true;
  error = '';

  ngOnInit(): void {
    this.loadNews();
  }

  refreshNews(): void {
    this.newsService.clearSearchCache();
    this.loadNews();
  }

  onFiltersChange(filters: NewsFilters): void {
    this.filters = { ...filters };

    if (this.pendingLoadId) {
      clearTimeout(this.pendingLoadId);
    }

    this.pendingLoadId = setTimeout(() => {
      this.pendingLoadId = null;
      this.loadNews();
    }, 350);
  }

  trackByArticle(_: number, article: NewsArticle): string {
    return article.id;
  }

  private loadNews(): void {
    const now = Date.now();

    if (this.rateLimitedUntil > now) {
      this.error = 'Rate limit reached. Please wait a few minutes and try again.';

      this.loading = false;
      return;
    }

    this.loading = true;
    this.error = '';

    this.newsService.searchNews(this.filters).subscribe({
      next: (articles) => {
        this.visibleArticles = [...articles].sort(
          (a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
        );
        this.loading = false;
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 429) {
          this.rateLimitedUntil = Date.now() + this.rateLimitWindowMs;
          this.error = 'Rate limit reached. Please wait a few minutes and try again.';
        } else {
          this.error = 'Unable to load news at the moment.';
        }
        this.loading = false;
      }
    });
  }
}