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

    // ---------------- 분실 신고 (S16, S17, S23) ----------------
    @POST("lost")
    Call<Models.LostOut> createLost(@Body Models.LostIn body);

    @Multipart
    @POST("lost/{id}/photo")
    Call<Models.LostOut> uploadLostPhoto(@Path("id") String id, @Part MultipartBody.Part image);

    /** tab = null(전체) / "open"(진행 중) / "done"(완료) */
    @GET("me/lost")
    Call<List<Models.LostOut>> myLost(@Query("tab") String tab);

    @GET("lost/{id}")
    Call<Models.LostOut> getLost(@Path("id") String id);

    @PATCH("lost/{id}")
    Call<Models.LostOut> updateLost(@Path("id") String id, @Body Models.LostIn body);

    /** '찾았어요' / '신고 종료' */
    @POST("lost/{id}/close")
    Call<Models.LostOut> closeLost(@Path("id") String id);

    @GET("me/summary")
    Call<Models.Summary> summary();

    @DELETE("me")
    Call<Models.Ok> deleteMe();
}
