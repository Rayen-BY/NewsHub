import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, map, of } from 'rxjs';
import { NewsArticle } from '../models/news.model';

interface SaveFavoriteResponse {
  message: string;
  news_id: number;
}

interface RemoveFavoriteResponse {
  message: string;
  removed: boolean;
}

interface CheckFavoriteResponse {
  saved: boolean;
  news_id: number | null;
}

@Injectable({
  providedIn: 'root'
})
export class FavoritesService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = 'http://127.0.0.1:8000';
    //service poste vers /favorites côté backend => main 383
  saveArticle(userId: number, article: NewsArticle): Observable<SaveFavoriteResponse> {
    return this.http.post<SaveFavoriteResponse>(`${this.apiBaseUrl}/favorites`, {
      user_id: userId,
      article: {
        article_id: article.id,
        title: article.title,
        description: article.description,
        content: article.content,
        image_url: article.imageUrl,
        source_url: article.url,
        source_name: article.sourceName,
        published_at: article.publishedAt,
        category: article.category
      }
    });
  }

  removeArticle(userId: number, articleUrl: string): Observable<RemoveFavoriteResponse> {
    return this.http.request<RemoveFavoriteResponse>('delete', `${this.apiBaseUrl}/favorites`, {
      body: {
        user_id: userId,
        article_url: articleUrl
      }
    });
  }

  isArticleSaved(userId: number, articleUrl: string): Observable<boolean> {
    const params = new HttpParams()
      .set('user_id', userId.toString())
      .set('article_url', articleUrl);

    return this.http.get<CheckFavoriteResponse>(`${this.apiBaseUrl}/favorites-status`, { params }).pipe(
      map((response) => response.saved),
      catchError(() => of(false))
    );
  }
}
