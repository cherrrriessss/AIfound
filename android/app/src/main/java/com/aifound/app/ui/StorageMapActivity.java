package com.aifound.app.ui;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.aifound.app.R;
import com.aifound.app.net.MatchModels;
import com.aifound.app.net.Models;
import com.aifound.app.util.Ui;

/**
 * S09 보관함 위치 안내 (이민서). 와이어프레임 S09_StorageMap.
 * 보관함 이름·코드·건물·찾아가는 길·운영 시간. 캠퍼스 지도는 휴대폰 지도 앱(geo:)으로 연다.
 * (보관함 좌표가 DB 에 생기면 앱 안 지도로 바꿀 수 있다)
 */
public class StorageMapActivity extends AppCompatActivity {

    private static final String SCHOOL = "숭실대학교";

    public static void open(Activity from, Models.Locker l) {
        open(from, l.name, l.code, l.building, l.location, l.hours);
    }

    public static void open(Activity from, MatchModels.LockerInfo l) {
        open(from, l.name, null, l.building, l.location, l.hours);
    }

    private static void open(Activity from, String name, String code, String building, String location, String hours) {
        from.startActivity(new Intent(from, StorageMapActivity.class)
                .putExtra("name", name).putExtra("code", code).putExtra("building", building)
                .putExtra("location", location).putExtra("hours", hours));
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_storage_map);
        Ui.header(this, "보관함 위치");
        Intent in = getIntent();
        String building = in.getStringExtra("building");

        ((TextView) findViewById(R.id.tvName)).setText(in.getStringExtra("name"));
        String code = in.getStringExtra("code");
        TextView tvCode = findViewById(R.id.tvCode);
        tvCode.setText(code != null ? "보관함 " + code : building);

        LinearLayout table = findViewById(R.id.infoTable);
        addRow(table, "건물", building);
        addRow(table, "찾아가는 길", in.getStringExtra("location"));
        addRow(table, "운영 시간", in.getStringExtra("hours"));

        findViewById(R.id.btnMap).setOnClickListener(v -> {
            String q = SCHOOL + " " + (building != null ? building : "");
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=" + Uri.encode(q))));
            } catch (ActivityNotFoundException e) {
                Toast.makeText(this, "지도 앱이 없어요", Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void addRow(LinearLayout table, String key, String value) {
        if (value == null || value.trim().isEmpty()) return;
        View row = LayoutInflater.from(this).inflate(R.layout.item_info_row, table, false);
        ((TextView) row.findViewById(R.id.tvKey)).setText(key);
        ((TextView) row.findViewById(R.id.tvValue)).setText(value);
        table.addView(row);
    }
}
