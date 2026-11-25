package com.aifound.app.ui;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.aifound.app.R;
import com.aifound.app.net.ApiCallback;
import com.aifound.app.net.ApiClient;
import com.aifound.app.net.Models;
import com.aifound.app.util.Fmt;
import com.aifound.app.util.TabBar;
import com.aifound.app.util.Ui;

import java.util.ArrayList;
import java.util.List;

/**
 * S23 내 분실 신고 (이민서). 와이어프레임 S23_MyLost.
 * GET /me/lost → '진행 중 n' / '완료 n' 토글. 단계: 매칭 대기 → 후보 있음 → 수령 대기 → 수령 완료.
 * 카드 버튼: 후보 보기(S18) · 수정(S16) · 찾았어요/신고 종료(POST /lost/{id}/close).
 */
public class MyLostActivity extends AppCompatActivity {

    private LinearLayout list;
    private SwipeRefreshLayout refresh;
    private TextView[] toggles;
    private boolean showDone;
    private final List<Models.LostOut> open = new ArrayList<>(), done = new ArrayList<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_list_tabs);
        Ui.header(this, "내 분실 신고");
        TabBar.setup(this, TabBar.MY);
        list = findViewById(R.id.list);
        refresh = findViewById(R.id.refresh);
        refresh.setOnRefreshListener(this::load);
        toggles = Ui.toggles(this, new String[]{"진행 중", "완료"}, 0, i -> {
            showDone = i == 1;
            render();
        });
        TextView footer = findViewById(R.id.tvFooter);
        footer.setText("상태: 매칭 대기 → 후보 있음 → 수령 대기 → 수령 완료");
        footer.setVisibility(View.VISIBLE);
    }

    @Override
    protected void onResume() {
        super.onResume();
        load();
    }

    private void load() {
        refresh.setRefreshing(true);
        ApiClient.get(this).myLost(null).enqueue(new ApiCallback<List<Models.LostOut>>(this) {
            @Override public void ok(List<Models.LostOut> all) {
                refresh.setRefreshing(false);
                open.clear();
                done.clear();
                for (Models.LostOut l : all) {
                    if ("closed".equals(l.stage) || "received".equals(l.stage)) done.add(l);
                    else open.add(l);
                }
                toggles[0].setText("진행 중 " + open.size());
                toggles[1].setText("완료 " + done.size());
                render();
            }

            @Override public void fail(String message) {
                super.fail(message);
                refresh.setRefreshing(false);
            }
        });
    }

    private void render() {
        list.removeAllViews();
        List<Models.LostOut> items = showDone ? done : open;
        if (items.isEmpty()) {
            list.addView(Ui.empty(this, showDone ? "완료된 신고가 없어요" : "진행 중인 분실 신고가 없어요.\n홈에서 분실 신고를 남길 수 있어요."));
            return;
        }
        LayoutInflater inf = LayoutInflater.from(this);
        for (Models.LostOut l : items) {
            View card = inf.inflate(R.layout.item_lost, list, false);
            bind(card, l);
            list.addView(card);
        }
    }

    private void bind(View card, Models.LostOut l) {
        ((TextView) card.findViewById(R.id.tvTitle)).setText(LostDoneActivity.title(l));
        ((TextView) card.findViewById(R.id.tvSub)).setText(
                Fmt.join(l.buildings, ", ") + " · " + Fmt.shortDate(l.createdAt) + " 신고");

        String label = "candidates".equals(l.stage) ? "후보 " + l.matchCount + "건"
                : (l.stageLabel != null ? l.stageLabel : "매칭 대기");
        boolean strong = "candidates".equals(l.stage) || "claimed".equals(l.stage);
        FrameLayout badgeBox = card.findViewById(R.id.badgeBox);
        badgeBox.addView(Ui.badge(this, label, strong));

        boolean active = !showDone;
        boolean hasCandidates = l.matchCount > 0 || "claimed".equals(l.stage);
        View candidates = card.findViewById(R.id.btnCandidates);
        View edit = card.findViewById(R.id.btnEdit);
        TextView close = card.findViewById(R.id.btnClose);
        candidates.setVisibility(active && hasCandidates ? View.VISIBLE : View.GONE);
        edit.setVisibility(active && !"claimed".equals(l.stage) ? View.VISIBLE : View.GONE);
        close.setVisibility(active ? View.VISIBLE : View.GONE);
        close.setText(hasCandidates ? "찾았어요" : "신고 종료");

        candidates.setOnClickListener(v -> MatchListActivity.open(this, l.id));
        edit.setOnClickListener(v -> LostReportActivity.openEdit(this, l.id));
        close.setOnClickListener(v -> confirmClose(l, hasCandidates));
        if (!active) ((View) candidates.getParent()).setVisibility(View.GONE);   // 완료 탭은 버튼 줄 없음
    }

    private void confirmClose(Models.LostOut l, boolean found) {
        new AlertDialog.Builder(this)
                .setTitle(found ? "물건을 찾았나요?" : "신고를 종료할까요?")
                .setMessage("신고를 닫으면 더 이상 매칭 알림이 오지 않아요.")
                .setPositiveButton(found ? "찾았어요" : "종료", (d, w) -> ApiClient.get(this).closeLost(l.id)
                        .enqueue(new ApiCallback<Models.LostOut>(this) {
                            @Override public void ok(Models.LostOut body) {
                                Toast.makeText(MyLostActivity.this, "신고를 닫았어요", Toast.LENGTH_SHORT).show();
                                load();
                            }
                        }))
                .setNegativeButton("취소", null)
                .show();
    }
}
