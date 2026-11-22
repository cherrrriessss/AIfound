package com.aifound.app.net;

import android.app.Activity;
import android.content.Intent;
import android.widget.Toast;

import com.aifound.app.data.TokenStore;
import com.aifound.app.ui.LoginActivity;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/**
 * Retrofit 콜백을 간단하게: 성공이면 ok(), 실패면 서버가 보낸 한국어 메시지를 토스트로.
 * 401(로그인 만료)이면 로그인 화면으로 보낸다.
 */
public abstract class ApiCallback<T> implements Callback<T> {
    private final Activity activity;

    protected ApiCallback(Activity activity) { this.activity = activity; }

    public abstract void ok(T body);

    /** 실패 시 추가로 할 일 (버튼 다시 켜기 등). 기본은 토스트만. */
    public void fail(String message) {
        Toast.makeText(activity, message, Toast.LENGTH_LONG).show();
    }

    @Override
    public void onResponse(Call<T> call, Response<T> response) {
        if (activity.isFinishing() || activity.isDestroyed()) return;
        if (response.isSuccessful() && response.body() != null) {
            ok(response.body());
            return;
        }
        if (response.code() == 401 && !(activity instanceof LoginActivity)) {
            TokenStore.clearToken(activity);
            Intent i = new Intent(activity, LoginActivity.class);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
            activity.startActivity(i);
            Toast.makeText(activity, "다시 로그인해 주세요.", Toast.LENGTH_SHORT).show();
            return;
        }
        fail(errorMessage(response));
    }

    @Override
    public void onFailure(Call<T> call, Throwable t) {
        if (activity.isFinishing() || activity.isDestroyed()) return;
        fail("서버에 연결할 수 없어요. 서버가 켜져 있는지, 서버 주소가 맞는지 확인해 주세요.");
    }

    /** 서버 오류 형식: {"detail": "한국어 문장"} 또는 {"detail": [검증 오류 목록]} */
    static String errorMessage(Response<?> response) {
        try {
            if (response.errorBody() != null) {
                JsonElement root = JsonParser.parseString(response.errorBody().string());
                if (root.isJsonObject()) {
                    JsonObject o = root.getAsJsonObject();
                    JsonElement d = o.get("detail");
                    if (d != null && d.isJsonPrimitive()) return d.getAsString();
                    if (d != null && d.isJsonArray()) return "입력한 값을 다시 확인해 주세요.";
                }
            }
        } catch (Exception ignored) {
            // 아래 기본 문구 사용
        }
        return "요청에 실패했어요 (" + response.code() + ")";
    }
}
