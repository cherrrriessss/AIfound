package com.aifound.app.ui;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.ImageView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;

import com.aifound.app.R;
import com.aifound.app.data.FoundDraft;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.ImageUtils;
import com.aifound.app.util.Steps;

import java.io.File;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** S10 사진 촬영·선택 → 사진 정리 → 서버 /found/analyze → S11 */
public class PhotoActivity extends AppCompatActivity {

    private ImageView ivPreview;
    private View loading, tvEmpty;
    private Uri cameraUri;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());

    private final ActivityResultLauncher<Uri> takePicture =
            registerForActivityResult(new ActivityResultContracts.TakePicture(), saved -> {
                if (Boolean.TRUE.equals(saved) && cameraUri != null) handlePhoto(cameraUri);
            });

    private final ActivityResultLauncher<String> pickImage =
            registerForActivityResult(new ActivityResultContracts.GetContent(), uri -> {
                if (uri != null) handlePhoto(uri);
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_photo);
        Steps.header(this, "습득물 등록", 1);

        ivPreview = findViewById(R.id.ivPreview);
        loading = findViewById(R.id.loading);
        tvEmpty = findViewById(R.id.tvEmpty);

        findViewById(R.id.btnCamera).setOnClickListener(v -> openCamera());
        findViewById(R.id.btnGallery).setOnClickListener(v -> pickImage.launch("image/*"));
    }

    /** 기본 카메라 앱으로 촬영 (CAMERA 권한 불필요) */
    private void openCamera() {
        File dir = new File(getCacheDir(), "images");
        if (!dir.exists() && !dir.mkdirs()) {
            Toast.makeText(this, "임시 폴더를 만들 수 없어요", Toast.LENGTH_SHORT).show();
            return;
        }
        File raw = new File(dir, "camera_raw.jpg");
        cameraUri = FileProvider.getUriForFile(this, getPackageName() + ".fileprovider", raw);
        takePicture.launch(cameraUri);
    }

    private void handlePhoto(Uri uri) {
        setLoading(true);
        io.execute(() -> {
            try {
                File jpeg = ImageUtils.prepareJpeg(this, uri);
                main.post(() -> {
                    ivPreview.setImageBitmap(ImageUtils.load(jpeg));
                    tvEmpty.setVisibility(View.GONE);
                    analyze(jpeg);
                });
            } catch (Exception e) {
                main.post(() -> {
                    setLoading(false);
                    Toast.makeText(this, "사진을 읽지 못했어요. 다른 사진으로 해 주세요.", Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void analyze(File jpeg) {
        ApiClient.get(this).analyze(ApiClient.imagePart(jpeg))
                .enqueue(new ApiCallback<Models.AnalyzeOut>(this) {
                    @Override public void ok(Models.AnalyzeOut body) {
                        setLoading(false);
                        FoundDraft d = FoundDraft.get();
                        d.imageFile = jpeg;
                        d.analysis = body;
                        d.attributes = body.attributes;   // S12 에서 수정
                        d.masks.clear();
                        startActivity(new Intent(PhotoActivity.this, MaskingActivity.class));
                    }

                    @Override public void fail(String message) {
                        super.fail(message);
                        setLoading(false);
                    }
                });
    }

    private void setLoading(boolean on) {
        loading.setVisibility(on ? View.VISIBLE : View.GONE);
        findViewById(R.id.btnCamera).setEnabled(!on);
        findViewById(R.id.btnGallery).setEnabled(!on);
    }

    @Override
    protected void onDestroy() {
        io.shutdown();
        super.onDestroy();
    }
}
