package com.aifound.app.ui;

import android.app.DatePickerDialog;
import android.app.TimePickerDialog;
import android.content.Intent;
import android.os.Bundle;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.Spinner;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.data.FoundDraft;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.util.Steps;
import com.google.android.material.button.MaterialButton;

import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.List;
import java.util.Locale;

/** S13 어디서 주웠나요? (건물, 상세 위치, 시간, 특징) */
public class FoundInfoActivity extends AppCompatActivity {

    private Spinner spBuilding;
    private EditText etPlace, etDesc;
    private MaterialButton btnDate, btnTime;
    private FoundDraft draft;
    private List<String> buildings;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        draft = FoundDraft.get();
        setContentView(R.layout.activity_found_info);
        Steps.header(this, "어디서 주웠나요?", 4);

        spBuilding = findViewById(R.id.spBuilding);
        etPlace = findViewById(R.id.etPlace);
        etDesc = findViewById(R.id.etDesc);
        btnDate = findViewById(R.id.btnDate);
        btnTime = findViewById(R.id.btnTime);

        etPlace.setText(draft.locationDetail);
        etDesc.setText(draft.description);
        showTime();

        btnDate.setOnClickListener(v -> new DatePickerDialog(this, (dp, y, m, d) -> {
            draft.foundAt.set(y, m, d);
            showTime();
        }, draft.foundAt.get(Calendar.YEAR), draft.foundAt.get(Calendar.MONTH),
                draft.foundAt.get(Calendar.DAY_OF_MONTH)).show());

        btnTime.setOnClickListener(v -> new TimePickerDialog(this, (tp, h, min) -> {
            draft.foundAt.set(Calendar.HOUR_OF_DAY, h);
            draft.foundAt.set(Calendar.MINUTE, min);
            showTime();
        }, draft.foundAt.get(Calendar.HOUR_OF_DAY), draft.foundAt.get(Calendar.MINUTE), false).show());

        findViewById(R.id.btnNow).setOnClickListener(v -> { draft.foundAt = Calendar.getInstance(); showTime(); });
        findViewById(R.id.btnHourAgo).setOnClickListener(v -> {
            Calendar c = Calendar.getInstance();
            c.add(Calendar.HOUR_OF_DAY, -1);
            draft.foundAt = c;
            showTime();
        });
        findViewById(R.id.btnMorning).setOnClickListener(v -> {
            Calendar c = Calendar.getInstance();
            c.set(Calendar.HOUR_OF_DAY, 10);
            c.set(Calendar.MINUTE, 0);
            draft.foundAt = c;
            showTime();
        });

        loadBuildings();
        findViewById(R.id.btnNext).setOnClickListener(v -> next());
    }

    private void loadBuildings() {
        ApiClient.get(this).buildings().enqueue(new ApiCallback<List<String>>(this) {
            @Override public void ok(List<String> body) {
                buildings = body;
                ArrayAdapter<String> ad = new ArrayAdapter<>(FoundInfoActivity.this,
                        android.R.layout.simple_spinner_item, body);
                ad.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                spBuilding.setAdapter(ad);
                for (int i = 0; i < body.size(); i++) {
                    if (body.get(i).equals(draft.building)) spBuilding.setSelection(i);
                }
            }
        });
    }

    private void showTime() {
        btnDate.setText(new SimpleDateFormat("M/d (E)", Locale.KOREA).format(draft.foundAt.getTime()));
        btnTime.setText(new SimpleDateFormat("a h:mm", Locale.KOREA).format(draft.foundAt.getTime()));
    }

    private void next() {
        if (buildings == null) {
            Toast.makeText(this, "건물 목록을 불러오는 중이에요", Toast.LENGTH_SHORT).show();
            return;
        }
        if (buildings.isEmpty() || spBuilding.getSelectedItem() == null) {
            // 실제 DB 에 lockers 데이터가 아직 없을 때 (서버 .env 의 CAMPUS_BUILDINGS 로도 채울 수 있음)
            Toast.makeText(this, "건물 목록이 비어 있어요. 보관함 데이터를 먼저 넣어 주세요.", Toast.LENGTH_LONG).show();
            return;
        }
        if (draft.foundAt.getTimeInMillis() > System.currentTimeMillis() + 60_000) {
            Toast.makeText(this, "주운 시간이 미래로 되어 있어요", Toast.LENGTH_SHORT).show();
            return;
        }
        draft.building = (String) spBuilding.getSelectedItem();
        String place = etPlace.getText().toString().trim();
        draft.locationDetail = place.isEmpty() ? null : place;
        String desc = etDesc.getText().toString().trim();
        draft.description = desc.isEmpty() ? null : desc;
        startActivity(new Intent(this, StorageActivity.class));
    }
}
