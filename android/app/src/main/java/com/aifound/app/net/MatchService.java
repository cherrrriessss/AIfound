package com.aifound.app.net;

import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.POST;
import retrofit2.http.PUT;
import retrofit2.http.Path;
import retrofit2.http.Query;

/** 주희선 매칭 서버(8000) API. match-server/README.md 4번 표. ApiClient.match(this) 로 부른다. */
public interface MatchService {

    @POST("devices")
    Call<Models.Ok> registerDevice(@Body MatchModels.DeviceIn body);                       // 03

    @GET("matches/summary")
    Call<MatchModels.Summary> summary();                                                  // 06 배너

    @GET("lost-reports/{id}/matches")
    Call<MatchModels.MatchList> matchesForLost(@Path("id") String lostId);               // 18

    @GET("matches/{id}")
    Call<MatchModels.MatchDetail> matchDetail(@Path("id") String matchId);               // 19

    @POST("matches/{id}/claim")
    Call<MatchModels.ClaimOut> claim(@Path("id") String matchId);                        // 19 내 물건이에요

    /** 08 '내 물건이에요' — 매칭 없이 바로 수령 요청. 응답의 matchId 로 S20 */
    @POST("found-items/{id}/claim")
    Call<MatchModels.ClaimOut> claimFound(@Path("id") String foundId);

    @POST("matches/{id}/reject")
    Call<Models.Ok> reject(@Path("id") String matchId, @Body MatchModels.RejectIn body); // 21

    @GET("matches/{id}/pickup")
    Call<MatchModels.PickupGuide> pickupGuide(@Path("id") String matchId);               // 20

    @GET("matches/{id}/pickup/code")
    Call<MatchModels.PickupCode> pickupCode(@Path("id") String matchId);                 // 20 (expires_in 초마다)

    @GET("matches/{id}/pickup/status")
    Call<MatchModels.PickupStatus> pickupStatus(@Path("id") String matchId);             // 20 수령 완료 확인

    /** kind = all / mine(내가 찾은 것) / given(내가 돌려준 것) */
    @GET("pickups")
    Call<MatchModels.PickupList> pickups(@Query("kind") String kind);                    // 25

    @GET("notifications")
    Call<MatchModels.NotificationList> notifications();                                  // 27

    @POST("notifications/read-all")
    Call<Models.Ok> readAll();                                                            // 27

    @GET("settings/notifications")
    Call<MatchModels.Settings> settings();                                               // 26

    @PUT("settings/notifications")
    Call<MatchModels.Settings> saveSettings(@Body MatchModels.Settings body);            // 26
}
