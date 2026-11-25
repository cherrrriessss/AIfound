package com.aifound.app.ui;

import android.app.Activity;
import android.app.DatePickerDialog;
import android.app.TimePickerDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.Spinner;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.Catalog;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.ImageUtils;
import com.aifound.app.util.Ui;
import com.google.android.material.button.MaterialButton;
import com.google.android.material.chip.Chip;
import com.google.android.material.chip.ChipGroup;

import java.io.File;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * S16 분실 신고 작성 (이민서). 와이어프레임 S16_LostReport.
 * POST /lost (김준희 서버) → 서버가 바로 매칭 서버를 불러서 결과를 match 에 담아 준다 → S17.
 * 참고 사진은 신고 저장 후 POST /lost/{id}/photo 로 따로 올린다.
 *
 * 같은 화면으로 S23 '수정'도 한다 (EXTRA_LOST_ID → PATCH /lost/{id}).
 * S08 '분실 신고하기'에서 오면 그 습득물의 종류·색·브랜드·건물을 미리 채운다.
 */
public class LostReportActivity extends AppCompatActivity {

    private static final String EXTRA_LOST_ID = "lost_id";
    private static final String EXTRA_CATEGORY = "category";
    private static final String EXTRA_COLOR = "color";
    private static final String EXTRA_BRAND = "brand";
    private static final String EXTRA_MODEL = "model";
    private static final String EXTRA_BUILDING = "building";

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");

    /** 새 신고 */
    public static void open(Activity from) {
        from.startActivity(new Intent(from, LostReportActivity.class));
    }

    /** S08 에서: 이 습득물 정보로 미리 채우기 */
    public static void openPrefilled(Activity from, Models.FoundOut f) {
        Intent i = new Intent(from, LostReportActivity.class)
                .putExtra(EXTRA_CATEGORY, f.category)
                .putExtra(EXTRA_COLOR, Fmt.attr(f.attrs, "color"))
                .putExtra(EXTRA_BRAND, Fmt.attr(f.attrs, "brand"))
                .putExtra(EXTRA_MODEL, Fmt.attr(f.attrs, "model"))
                .putExtra(EXTRA_BUILDING, f.building);
        from.startActivity(i);
    }

    /** S23 '수정' */
    public static void openEdit(Activity from, String lostId) {
        from.startActivity(new Intent(from, LostReportActivity.class).putExtra(EXTRA_LOST_ID, lostId));
    }

    private ChipGroup categoryGroup, buildingGroup;
    private Spinner spColor;
    private EditText etBrand, etModel, etDesc;
    private MaterialButton btnDate, btnFrom, btnTo, btnSubmit;
    private View progress;

    private String editId;                 // null 이면 새 신고
    private final Set<String> buildings = new LinkedHashSet<>();
    private List<String> allBuildings;
    private LocalDate date = LocalDate.now(KST);
    private LocalTime from, to;
    private File photo;                    // 고른 참고 사진 (EXIF 지우고 줄인 JPEG)

    private final ActivityResultLauncher<String> pickImage =
            registerForActivityResult(new ActivityResultContracts.GetContent(), this::onPhotoPicked);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_lost_report);
        editId = getIntent().getStringExtra(EXTRA_LOST_ID);
        Ui.header(this, editId == null ? "분실 신고" : "신고 수정");

        categoryGroup = findViewById(R.id.categoryGroup);
        buildingGroup = findViewById(R.id.buildingGroup);
        spColor = findViewById(R.id.spColor);
        etBrand = findViewById(R.id.etBrand);
        etModel = findViewById(R.id.etModel);
        etDesc = findViewById(R.id.etDesc);
        btnDate = findViewById(R.id.btnDate);
        btnFrom = findViewById(R.id.btnFrom);
        btnTo = findViewById(R.id.btnTo);
        btnSubmit = findViewById(R.id.btnSubmit);
        progress = findViewById(R.id.progress);

        for (String c : Catalog.CATEGORIES) Ui.choiceChip(this, categoryGroup, c);
        ArrayAdapter<String> colors = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, Catalog.COLORS);
        colors.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spColor.setAdapter(colors);

        // 기본 시간대: 지금부터 3시간 전 ~ 지금 (정각 기준)
        LocalTime now = LocalTime.now(KST).withMinute(0).withSecond(0).withNano(0);
        to = now.plusHours(1).equals(LocalTime.MIDNIGHT) ? LocalTime.of(23, 59) : now.plusHours(1);
        from = now.getHour() >= 3 ? now.minusHours(3) : LocalTime.MIDNIGHT;
        showTime();

        btnDate.setOnClickListener(v -> new DatePickerDialog(this, (dp, y, m, d) -> {
            date = LocalDate.of(y, m + 1, d);
            showTime();
        }, date.getYear(), date.getMonthValue() - 1, date.getDayOfMonth()).show());
        btnFrom.setOnClickListener(v -> new TimePickerDialog(this, (tp, h, min) -> {
            from = LocalTime.of(h, min);
            showTime();
        }, from.getHour(), from.getMinute(), false).show());
        btnTo.setOnClickListener(v -> new TimePickerDialog(this, (tp, h, min) -> {
            to = LocalTime.of(h, min);
            showTime();
        }, to.getHour(), to.getMinute(), false).show());

        findViewById(R.id.btnPhoto).setOnClickListener(v -> pickImage.launch("image/*"));
        btnSubmit.setOnClickListener(v -> submit());
        if (editId != null) {
            btnSubmit.setText("수정하기");
            findViewById(R.id.photoRow).setVisibility(View.GONE);   // 사진은 새 신고 때만
            loadForEdit();
        } else {
            prefill();
        }
        loadBuildings();
    }

    // ---------------- 미리 채우기 ----------------

    private void prefill() {
        Intent in = getIntent();
        selectCategory(in.getStringExtra(EXTRA_CATEGORY));
        selectColor(in.getStringExtra(EXTRA_COLOR));
        setText(etBrand, in.getStringExtra(EXTRA_BRAND));
        setText(etModel, in.getStringExtra(EXTRA_MODEL));
        String b = in.getStringExtra(EXTRA_BUILDING);
        if (b != null) buildings.add(b);
        renderBuildings();
    }

    private void loadForEdit() {
        ApiClient.get(this).getLost(editId).enqueue(new ApiCallback<Models.LostOut>(this) {
            @Override public void ok(Models.LostOut l) {
                selectCategory(l.category);
                selectColor(Fmt.attr(l.attrs, "color"));
                setText(etBrand, Fmt.attr(l.attrs, "brand"));
                setText(etModel, Fmt.attr(l.attrs, "model"));
                setText(etDesc, l.description);
                buildings.clear();
                buildings.addAll(l.buildings);
                renderBuildings();
                ZonedDateTime a = Fmt.parse(l.lostFrom), b = Fmt.parse(l.lostTo);
                if (a != null && b != null) {
                    date = a.toLocalDate();
                    from = a.toLocalTime().withSecond(0).withNano(0);
                    to = b.toLocalTime().withSecond(0).withNano(0);
                    showTime();
                }
            }
        });
    }

    private void selectCategory(String c) {
        int idx = c == null ? 0 : Catalog.indexOf(Catalog.CATEGORIES, c);
        ((Chip) categoryGroup.getChildAt(idx)).setChecked(true);
    }

    private void selectColor(String c) {
        spColor.setSelection(c == null ? 0 : Catalog.indexOf(Catalog.COLORS, c));
    }

    private static void setText(EditText et, String v) {
        if (v != null) et.setText(v);
    }

    // ---------------- 건물 (여러 개) ----------------

    private void loadBuildings() {
        ApiClient.get(this).buildings().enqueue(new ApiCallback<List<String>>(this) {
            @Override public void ok(List<String> body) { allBuildings = body; }
        });
    }

    private void renderBuildings() {
        buildingGroup.removeAllViews();
        for (String b : buildings) {
            Chip chip = new Chip(this);
            chip.setText(b);
            chip.setTextSize(13);
            chip.setCloseIconVisible(true);
            chip.setCloseIconContentDescription(b + " 빼기");
            chip.setChipBackgroundColorResource(R.color.surface_soft);
            chip.setEnsureMinTouchTargetSize(false);
            chip.setOnCloseIconClickListener(v -> {
                buildings.remove(b);
                renderBuildings();
            });
            buildingGroup.addView(chip);
        }
        Chip add = new Chip(this);
        add.setText("+ 건물 추가");
        add.setTextSize(13);
        add.setChipBackgroundColorResource(R.color.white);
        add.setChipStrokeColorResource(R.color.line);
        add.setChipStrokeWidth(Fmt.dp(this, 1));
        add.setEnsureMinTouchTargetSize(false);
        add.setOnClickListener(v -> pickBuildings());
        buildingGroup.addView(add);
    }

    private void pickBuildings() {
        if (allBuildings == null) {
            Toast.makeText(this, "건물 목록을 불러오는 중이에요", Toast.LENGTH_SHORT).show();
            loadBuildings();
            return;
        }
        if (allBuildings.isEmpty()) {
            Toast.makeText(this, "건물 목록이 비어 있어요. 보관함 데이터를 먼저 넣어 주세요.", Toast.LENGTH_LONG).show();
            return;
        }
        String[] names = allBuildings.toArray(new String[0]);
        boolean[] checked = new boolean[names.length];
        for (int i = 0; i < names.length; i++) checked[i] = buildings.contains(names[i]);
        new AlertDialog.Builder(this)
                .setTitle("잃어버린 곳 (여러 개 선택)")
                .setMultiChoiceItems(names, checked, (d, which, on) -> checked[which] = on)
                .setPositiveButton("확인", (d, w) -> {
                    buildings.clear();
                    for (int i = 0; i < names.length; i++) if (checked[i]) buildings.add(names[i]);
                    renderBuildings();
                })
                .setNegativeButton("취소", null)
                .show();
    }

    // ---------------- 시간 ----------------

    private void showTime() {
        btnDate.setText(date.format(DateTimeFormatter.ofPattern("M/d (E)", Locale.KOREAN)));
        DateTimeFormatter t = DateTimeFormatter.ofPattern("a h:mm", Locale.KOREAN);
        btnFrom.setText(from.format(t));
        btnTo.setText(to.format(t));
    }

    // ---------------- 사진 ----------------

    private void onPhotoPicked(Uri uri) {
        if (uri == null) return;
        try {
            photo = ImageUtils.prepareJpeg(this, uri);    // 1600px 로 줄이고 EXIF(위치) 제거
            ImageView iv = findViewById(R.id.ivPhoto);
            iv.setImageBitmap(ImageUtils.load(photo));
            iv.setVisibility(View.VISIBLE);
            findViewById(R.id.ivPhotoIcon).setVisibility(View.GONE);
        } catch (Exception e) {
            Toast.makeText(this, "사진을 불러오지 못했어요", Toast.LENGTH_SHORT).show();
        }
    }

    // ---------------- 보내기 ----------------

    private void submit() {
        Chip cat = findViewById(categoryGroup.getCheckedChipId());
        if (cat == null) {
            Toast.makeText(this, "무엇을 잃어버렸는지 골라 주세요", Toast.LENGTH_SHORT).show();
            return;
        }
        if (buildings.isEmpty()) {
            Toast.makeText(this, "잃어버린 곳을 하나 이상 골라 주세요", Toast.LENGTH_SHORT).show();
            return;
        }
        ZonedDateTime start = date.atTime(from).atZone(KST);
        ZonedDateTime end = date.atTime(to).atZone(KST);
        if (!end.isAfter(start)) {
            Toast.makeText(this, "끝 시간이 시작 시간보다 뒤여야 해요", Toast.LENGTH_SHORT).show();
            return;
        }
        if (start.isAfter(ZonedDateTime.now(KST))) {
            Toast.makeText(this, "잃어버린 시간이 미래로 되어 있어요", Toast.LENGTH_SHORT).show();
            return;
        }

        Models.LostIn body = new Models.LostIn();
        body.category = cat.getText().toString();
        body.color = (String) spColor.getSelectedItem();
        body.brand = textOrNull(etBrand);
        body.model = textOrNull(etModel);
        body.description = textOrNull(etDesc);
        body.buildings = new ArrayList<>(buildings);
        body.lostFrom = start.toOffsetDateTime().toString();
        body.lostTo = end.toOffsetDateTime().toString();

        busy(true);
        if (editId != null) {
            ApiClient.get(this).updateLost(editId, body).enqueue(new ApiCallback<Models.LostOut>(this) {
                @Override public void ok(Models.LostOut l) {
                    Toast.makeText(LostReportActivity.this, "수정했어요. AI가 다시 비교해요.", Toast.LENGTH_SHORT).show();
                    finish();
                }

                @Override public void fail(String message) { super.fail(message); busy(false); }
            });
            return;
        }
        ApiClient.get(this).createLost(body).enqueue(new ApiCallback<Models.LostOut>(this) {
            @Override public void ok(Models.LostOut l) {
                if (photo != null) uploadPhoto(l);
                else done(l);
            }

            @Override public void fail(String message) { super.fail(message); busy(false); }
        });
    }

    /** 참고 사진은 신고가 저장된 뒤 따로. 실패해도 신고는 이미 저장됐으니 S17 로 간다. */
    private void uploadPhoto(Models.LostOut saved) {
        ApiClient.get(this).uploadLostPhoto(saved.id, ApiClient.imagePart(photo))
                .enqueue(new ApiCallback<Models.LostOut>(this) {
                    @Override public void ok(Models.LostOut l) {
                        l.match = saved.match;      // 매칭 결과는 처음 응답에만 있다
                        done(l);
                    }

                    @Override public void fail(String message) {
                        Toast.makeText(LostReportActivity.this, "사진은 올리지 못했어요. 신고는 접수됐어요.", Toast.LENGTH_LONG).show();
                        done(saved);
                    }
                });
    }

    private void done(Models.LostOut l) {
        LostDoneActivity.open(this, l);
        finish();
    }

    private void busy(boolean on) {
        btnSubmit.setEnabled(!on);
        btnSubmit.setText(on ? "" : (editId == null ? "신고하기" : "수정하기"));
        progress.setVisibility(on ? View.VISIBLE : View.GONE);
    }

    private static String textOrNull(EditText et) {
        String s = et.getText().toString().trim();
        return s.isEmpty() ? null : s;
    }
}
