package com.aifound.app.net;

import android.content.Context;

import com.aifound.app.data.TokenStore;
import com.google.gson.FieldNamingPolicy;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.File;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.logging.HttpLoggingInterceptor;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

/** Retrofit 준비. 모든 요청에 로그인 토큰(Bearer)을 자동으로 붙인다. */
public final class ApiClient {
    private static ApiService service;
    private static String currentBaseUrl;
    private static final Gson GSON = new GsonBuilder()
            .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
            .create();

    private ApiClient() {}

    public static Gson gson() { return GSON; }

    private static MatchService matchService;
    private static String currentMatchUrl;

    public static synchronized ApiService get(Context context) {
        final Context app = context.getApplicationContext();
        String baseUrl = TokenStore.baseUrl(app);
        if (service == null || !baseUrl.equals(currentBaseUrl)) {
            service = retrofit(app, baseUrl).create(ApiService.class);
            currentBaseUrl = baseUrl;
        }
        return service;
    }

    /** 주희선 매칭 서버(8000): 매칭·수령·알림. 로그인 토큰은 같은 것을 쓴다. */
    public static synchronized MatchService match(Context context) {
        final Context app = context.getApplicationContext();
        String url = TokenStore.matchUrl(app);
        if (matchService == null || !url.equals(currentMatchUrl)) {
            matchService = retrofit(app, url).create(MatchService.class);
            currentMatchUrl = url;
        }
        return matchService;
    }

    private static Retrofit retrofit(Context app, String baseUrl) {
        HttpLoggingInterceptor logging = new HttpLoggingInterceptor();
        logging.setLevel(HttpLoggingInterceptor.Level.BASIC);   // Logcat 에서 요청 확인 가능

        OkHttpClient http = new OkHttpClient.Builder()
                .addInterceptor(chain -> {
                    Request.Builder b = chain.request().newBuilder();
                    String token = TokenStore.token(app);
                    if (token != null) b.header("Authorization", "Bearer " + token);
                    return chain.proceed(b.build());
                })
                .addInterceptor(logging)
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(90, TimeUnit.SECONDS)     // Gemini 응답 대기
                .writeTimeout(60, TimeUnit.SECONDS)
                .build();

        return new Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(http)
                .addConverterFactory(GsonConverterFactory.create(GSON))
                .build();
    }

    /** 사진 파일 → multipart 'image' 필드 */
    public static MultipartBody.Part imagePart(File jpeg) {
        RequestBody body = RequestBody.create(jpeg, MediaType.get("image/jpeg"));
        return MultipartBody.Part.createFormData("image", "photo.jpg", body);
    }

    /** 객체 → multipart 텍스트 필드 (서버의 Form 'data') */
    public static RequestBody jsonPart(Object value) {
        return RequestBody.create(GSON.toJson(value), MediaType.get("text/plain; charset=utf-8"));
    }
}
