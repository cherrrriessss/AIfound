package com.aifound.app.ui;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;

import com.aifound.app.R;
import com.aifound.app.data.TokenStore;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.Steps;
import com.google.android.material.button.MaterialButton;

/** S03 최초 프로필 설정 (이름, 학과, 알림 허용). FCM 토큰 저장은 주희선 파트에서 PATCH /me 로 추가. */
public class ProfileActivity extends AppCompatActivity {

    private EditText etName, etDept;
    private MaterialButton btnNotify, btnStart;

    private final ActivityResultLauncher<String> notifyPermission =
            registerForActivityResult(new ActivityResultContracts.RequestPermission(), granted -> {
                updateNotifyButton();
                if (!granted) Toast.makeText(this, "설정에서 언제든 알림을 켤 수 있어요", Toast.LENGTH_SHORT).show();
            });

    private static final String EXTRA_EDIT = "edit";
    private boolean edit;          // S28 '프로필 수정'에서 왔으면 true → 저장 후 그냥 닫기

    /** S28 설정 → 프로필 수정 (이민서 추가) */
    public static void openEdit(android.app.Activity from) {
        from.startActivity(new Intent(from, ProfileActivity.class).putExtra(EXTRA_EDIT, true));
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_profile);
        edit = getIntent().getBooleanExtra(EXTRA_EDIT, false);
        Steps.header(this, edit ? "프로필 수정" : "프로필 설정", 0);

        etName = findViewById(R.id.etName);
        etDept = findViewById(R.id.etDept);
        btnNotify = findViewById(R.id.btnNotify);
        btnStart = findViewById(R.id.btnStart);
        ((TextView) findViewById(R.id.tvVerified)).setText(TokenStore.email(this) + " 인증 완료");

        btnNotify.setOnClickListener(v -> {
            if (Build.VERSION.SDK_INT >= 33) {
                notifyPermission.launch(Manifest.permission.POST_NOTIFICATIONS);
            } else {
                Toast.makeText(this, "알림이 이미 허용돼 있어요", Toast.LENGTH_SHORT).show();
            }
        });
        updateNotifyButton();
        btnStart.setOnClickListener(v -> save());
        if (edit) {
            btnStart.setText("저장");
            ApiClient.get(this).me().enqueue(new ApiCallback<Models.Profile>(this) {
                @Override public void ok(Models.Profile p) {
                    if (p.name != null) etName.setText(p.name);
                    if (p.department != null) etDept.setText(p.department);
                }
            });
        }
    }

    private void updateNotifyButton() {
        boolean granted = Build.VERSION.SDK_INT < 33 || ContextCompat.checkSelfPermission(this,
                Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED;
        btnNotify.setText(granted ? "알림 허용됨" : "알림 허용하기");
        btnNotify.setEnabled(!granted);
    }

    private void save() {
        String name = etName.getText().toString().trim();
        if (name.isEmpty()) {
            etName.setError("이름을 입력해 주세요");
            return;
        }
        String dept = etDept.getText().toString().trim();
        btnStart.setEnabled(false);
        ApiClient.get(this).updateMe(new Models.ProfileUpdate(name, dept.isEmpty() ? null : dept))
                .enqueue(new ApiCallback<Models.Profile>(this) {
                    @Override public void ok(Models.Profile body) {
                        if (edit) {
                            Toast.makeText(ProfileActivity.this, "저장했어요", Toast.LENGTH_SHORT).show();
                            finish();
                            return;
                        }
                        // 처음 가입이면 S04 온보딩 → 홈
                        Intent i = new Intent(ProfileActivity.this,
                                TokenStore.onboarded(ProfileActivity.this) ? HomeActivity.class : OnboardingActivity.class);
                        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                        startActivity(i);
                    }

                    @Override public void fail(String message) {
                        super.fail(message);
                        btnStart.setEnabled(true);
                    }
                });
    }
}
