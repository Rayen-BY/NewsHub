import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { NewsDetailsPageComponent } from './news-details-page';
import { FavoritesService } from '../../../core/services/favorites';
import { CommentsService } from '../../../core/services/comments';
import { NewsService } from '../../../core/services/news';

describe('NewsDetailsPageComponent', () => {
  let component: NewsDetailsPageComponent;
  let fixture: ComponentFixture<NewsDetailsPageComponent>;
  let routerSpy: jasmine.SpyObj<Router>;
  let favoritesServiceSpy: jasmine.SpyObj<FavoritesService>;

  beforeEach(async () => {
    routerSpy = jasmine.createSpyObj<Router>('Router', ['navigate'], { url: '/details/123' });
    favoritesServiceSpy = jasmine.createSpyObj<FavoritesService>('FavoritesService', [
      'saveArticle',
      'removeArticle',
      'isArticleSaved'
    ]);

    favoritesServiceSpy.isArticleSaved.and.returnValue(of(false));

    await TestBed.configureTestingModule({
      imports: [NewsDetailsPageComponent],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: { get: () => '123' },
              queryParamMap: { get: () => null }
            }
          }
        },
        { provide: Router, useValue: routerSpy },
        { provide: FavoritesService, useValue: favoritesServiceSpy },
        {
          provide: CommentsService,
          useValue: {
            getComments: jasmine.createSpy().and.returnValue(of([])),
            addComment: jasmine.createSpy().and.returnValue(of(null))
          }
        },
        {
          provide: NewsService,
          useValue: {
            getArticleById: jasmine.createSpy().and.returnValue(of(null))
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(NewsDetailsPageComponent);
    component = fixture.componentInstance;
    component.article = {
      id: '123',
      title: 'Test article',
      description: 'Test description',
      content: 'Test content',
      imageUrl: 'https://example.com/image.jpg',
      sourceName: 'Source',
      publishedAt: '2026-04-10T00:00:00.000Z',
      url: 'https://example.com/article',
      category: 'technology',
      readTime: 5
    };
    component.loginReturnUrl = '/details/123';
    localStorage.setItem('currentUser', JSON.stringify({ id: 7 }));
  });

  afterEach(() => {
    localStorage.removeItem('currentUser');
  });

  it('should redirect to login when saving returns an auth error', () => {
    favoritesServiceSpy.saveArticle.and.returnValue(throwError(() => ({ status: 401 })));

    component.toggleSaveArticle();

    expect(routerSpy.navigate).toHaveBeenCalledWith(['/login'], {
      queryParams: { returnUrl: '/details/123' }
    });
    expect(component.saveError).toBe('');
    expect(component.isSaving).toBeFalse();
  });
});