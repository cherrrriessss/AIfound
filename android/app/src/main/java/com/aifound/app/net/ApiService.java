package com.aifound.app.net;

import java.util.List;

import okhttp3.MultipartBody;
import okhttp3.RequestBody;
import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.DELETE;
import retrofit2.http.GET;
import retrofit2.http.Multipart;
import retrofit2.http.PATCH;
import retrofit2.http.POST;
import retrofit2.http.Part;
import retrofit2.http.Path;
import retrofit2.http.Query;

/** 김준희 서버 API 목록 (백엔드 README 4번 표). 매칭·알림·수령은 주희선 서버. */
public interface ApiService {

    @POST("auth/request-code")
    Call<Models.RequestCodeOut> requestCode(@Body Models.RequestCodeIn body);

    @POST("auth/verify")
    Call<Models.TokenOut> verify(@Body Models.VerifyIn body);

    @GET("me")
    Call<Models.Profile> me();

    @PATCH("me")
    Call<Models.Profile> updateMe(@Body Models.ProfileUpdate body);

    @GET("buildings")
    Call<List<String>> buildings();

    @GET("lockers")
    Call<List<Models.Locker>> lockers(@Query("building") String building);

    @Multipart
    @POST("found/analyze")
    Call<Models.AnalyzeOut> analyze(@Part MultipartBody.Part image);

    @Multipart
    @POST("found")
    Call<Models.FoundOut> createFound(@Part MultipartBody.Part image, @Part("data") RequestBody data);

    @GET("me/found")
    Call<List<Models.FoundOut>> myFound();

    /** S07 찾아보기 / S06 최근 습득물. null 인 값은 Retrofit 이 쿼리에서 뺀다. 날짜는 ISO 문자열. */
    @GET("found")
    Call<Models.FoundListOut> listFound(@Query("q") String q,
                                        @Query("category") String category,
                                        @Query("color") String color,
                                        @Query("building") String building,
                                        @Query("date_from") String dateFrom,
                                        @Query("date_to") String dateTo,
                                        @Query("page") int page,
                                        @Query("size") int size);

    @GET("found/{id}")
    Call<Models.FoundOut> getFound(@Path("id") String id);

    @GET("me/summary")
    Call<Models.Summary> summary();

    @DELETE("me")
    Call<Models.Ok> deleteMe();
}
