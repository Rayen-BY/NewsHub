import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, forkJoin, map, of, shareReplay, catchError, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { NewsCategory } from '../models/category.model';
import { NewsFilters } from '../models/filter.model';
import { NewsApiArticle, NewsApiResponse, NewsArticle, NewsStore } from '../models/news.model';

type RealCategory = Exclude<NewsCategory, 'all'>;

@Injectable({
  providedIn: 'root'
})
export class NewsService {
  private readonly http = inject(HttpClient);
  private readonly searchCachePrefix = 'news-search-cache:';

  private readonly categories: RealCategory[] = [
    'technology',
    'business',
    'politics',
    'science',
    'entertainment',
    'sports',
    'health'
  ];

  private newsStore$?: Observable<NewsStore>;

  getCategories(): RealCategory[] {
    return [...this.categories];
  }

  getAllNews(): Observable<NewsStore> {
    if (!this.newsStore$) {
      const requests = this.categories.reduce((acc, category) => {
        acc[category] = this.getNewsByCategory(category);
        return acc;
      }, {} as Record<RealCategory, Observable<NewsArticle[]>>);

      this.newsStore$ = forkJoin(requests).pipe(shareReplay(1));
    }

    return this.newsStore$;
  }

  getArticleById(articleId: string, category?: RealCategory): Observable<NewsArticle | null> {
    if (category) {
      return this.getNewsByCategory(category).pipe(
        map((articles) => articles.find((article) => article.id === articleId) || null)
      );
    }

    return this.getAllNews().pipe(
      map((store) => {
        const allArticles = [
          ...store.technology,
          ...store.business,
          ...store.politics,
          ...store.science,
          ...store.entertainment,
          ...store.sports,
          ...store.health
        ];

        return allArticles.find((article) => article.id === articleId) || null;
      })
    );
  }

  getNewsByCategory(category: RealCategory): Observable<NewsArticle[]> {
    const params = new HttpParams()
      .set('apikey', environment.newsApiKey)
      .set('category', category)
      .set('language', 'en')
      .set('size', '5');

    return this.http.get<NewsApiResponse>(environment.apiBaseUrl, { params }).pipe(
      map((response) =>
        (response.results ?? []).map((item, index) => this.mapArticle(item, category, index))
      ),
      map((articles) => articles.filter((article) => !!article.title)),
      map((articles) => this.dedupeArticles(articles)),
      catchError((error) => {
        console.error(`Failed to load ${category} news`, error);
        return of([]);
      })
    );
  }

  searchNews(filters: NewsFilters): Observable<NewsArticle[]> {
    const cacheKey = this.buildSearchCacheKey(filters);
    const cachedArticles = this.readCachedSearch(cacheKey);

    if (cachedArticles) {
      return of(cachedArticles);
    }

    let params = new HttpParams()
      .set('apikey', environment.newsApiKey)
      .set('language', 'en')
      .set('size', '10');

    if (filters.category !== 'all') {
      params = params.set('category', filters.category);
    }

    if (filters.country) {
      params = params.set('country', filters.country);
    }

    if (filters.source) {
      params = params.set('domainurl', filters.source);
    }

    if (filters.date) {
      params = params.set('from_date', filters.date).set('to_date', filters.date);
    }

    if (filters.dataType) {
      params = params.set('datatype', filters.dataType);
    }

    return this.http.get<NewsApiResponse>(environment.apiBaseUrl, { params }).pipe(
      map((response) => {
        const fallbackCategory: RealCategory =
          filters.category === 'all' ? 'technology' : filters.category;

        return (response.results ?? []).map((item, index) =>
          this.mapArticle(item, this.resolveCategory(item.category, fallbackCategory), index)
        );
      }),
      map((articles) => articles.filter((article) => !!article.title)),
      map((articles) => this.dedupeArticles(articles)),
      tap((articles) => this.writeCachedSearch(cacheKey, articles))
    );
  }

  clearSearchCache(): void {
    try {
      const keysToRemove: string[] = [];

      for (let index = 0; index < sessionStorage.length; index += 1) {
        const key = sessionStorage.key(index);

        if (key && key.startsWith(this.searchCachePrefix)) {
          keysToRemove.push(key);
        }
      }

      for (const key of keysToRemove) {
        sessionStorage.removeItem(key);
      }
    } catch {
      // Ignore storage errors.
    }
  }

  private buildSearchCacheKey(filters: NewsFilters): string {
    return JSON.stringify({
      category: filters.category,
      country: filters.country ?? '',
      source: filters.source ?? '',
      date: filters.date ?? '',
      dataType: filters.dataType ?? ''
    });
  }

  private readCachedSearch(cacheKey: string): NewsArticle[] | null {
    try {
      const rawValue = sessionStorage.getItem(`${this.searchCachePrefix}${cacheKey}`);

      if (!rawValue) {
        return null;
      }

      const parsed = JSON.parse(rawValue) as NewsArticle[];
      return Array.isArray(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }

  private writeCachedSearch(cacheKey: string, articles: NewsArticle[]): void {
    try {
      sessionStorage.setItem(`${this.searchCachePrefix}${cacheKey}`, JSON.stringify(articles));
    } catch {
      // Ignore storage errors.
    }
  }

  private mapArticle(item: NewsApiArticle, category: RealCategory, index: number): NewsArticle {
    console.log(`[NewsService] Article received - Title: ${item.title?.slice(0, 30)}...`, {
      description: item.description,
      content: item.content ? 'Available' : 'Missing'
    });

    const title = this.stripHtmlTags(item.title?.trim() || 'Untitled article');
    
    // Improved description fallback logic
    const rawDescription = this.stripHtmlTags(
      item.description?.trim() || 
      item.content?.trim() || 
      'No description available for this article.'
    );
    
    const content = this.resolveReadableContent(item.content, rawDescription);
    const id = item.article_id || `${category}-${index}-${title}`;

    return {
      id,
      title,
      description: this.truncateText(rawDescription, 160), // Increased from 120
      content: this.stripHtmlTags(content),
      imageUrl: item.image_url || this.getFallbackImage(category),
      sourceName: item.source_name || item.source_id || 'Unknown source',
      publishedAt: item.pubDate || new Date().toISOString(),
      readTime: this.estimateReadTime(content || rawDescription || title),
      url: item.link || '#',
      category
    };
  }

  private resolveCategory(
    apiCategories: string[] | undefined,
    fallbackCategory: RealCategory
  ): RealCategory {
    const firstCategory = apiCategories?.[0]?.toLowerCase();

    if (
      firstCategory === 'technology' ||
      firstCategory === 'business' ||
      firstCategory === 'politics' ||
      firstCategory === 'science' ||
      firstCategory === 'entertainment' ||
      firstCategory === 'sports' ||
      firstCategory === 'health'
    ) {
      return firstCategory;
    }

    return fallbackCategory;
  }

  private resolveReadableContent(content: string | undefined, fallbackDescription: string): string {
    const safeContent = content?.trim();

    if (!safeContent) {
      return fallbackDescription;
    }

    const blockedPhrases = [
      'available only in paid plans',
      'available in paid plans',
      'only available in paid plans',
      'disponible uniquement dans les forfaits payants',
      'متاح فقط في الخطط المدفوعة', // Arabic
      'disponible solo en planes de pago', // Spanish
      'nur in kostenpflichtigen plänen verfügbar', // German
      'disponível apenas em planos pagos', // Portuguese
      'disponibile solo nei piani a pagamento', // Italian
      '仅在付费套餐中提供', // Chinese
      'premium subscribers',
      'upgrade to premium',
      'subscribe to continue reading'
    ];

    const normalized = safeContent.toLowerCase();
    const hasBlockedPhrase = blockedPhrases.some((phrase) => normalized.includes(phrase));

    return hasBlockedPhrase ? fallbackDescription : safeContent;
  }

  private truncateText(text: string, maxLength: number): string {
    if (text.length <= maxLength) {
      return text;
    }

    return `${text.slice(0, maxLength).trimEnd()}...`;
  }

  private stripHtmlTags(text: string): string {
    if (!text) return '';
    return text.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ');
  }

  private dedupeArticles(articles: NewsArticle[]): NewsArticle[] {
    const uniqueMap = new Map<string, NewsArticle>();

    for (const article of articles) {
      const key = this.buildArticleKey(article);

      if (!uniqueMap.has(key)) {
        uniqueMap.set(key, article);
      }
    }

    return Array.from(uniqueMap.values());
  }

  private buildArticleKey(article: NewsArticle): string {
    const safeUrl = article.url && article.url !== '#' ? article.url.trim().toLowerCase() : '';
    const safeTitle = article.title.trim().toLowerCase();
    const safeSource = article.sourceName.trim().toLowerCase();

    return safeUrl || `${safeTitle}__${safeSource}`;
  }

  private estimateReadTime(text: string): number {
    const words = text.trim().split(/\s+/).filter(Boolean).length;
    return Math.max(3, Math.ceil(words / 200));
  }

  private getFallbackImage(category: RealCategory): string {
    return `https://placehold.co/800x500?text=${category}`;
  }
}