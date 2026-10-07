package kr.co.novalabs.maeumjangbu;

import android.Manifest;
import android.app.Activity;
import android.content.ContentResolver;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.provider.ContactsContract;

import androidx.activity.result.ActivityResult;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

import java.util.HashMap;
import java.util.Map;

/**
 * 연락처에서 이름 가져오기 (읽기 전용). 전화번호는 읽지 않는다.
 *
 * - pick(): 안드로이드 기본 연락처 선택 화면. 사용자가 고른 1명에 대해서만 임시로 읽을 수 있어 권한이 필요 없다.
 * - list(): 여러 명 불러오기. 이때만 READ_CONTACTS(읽기) 권한을 요청한다. 쓰기 권한은 요청하지 않는다.
 *
 * 커뮤니티 연락처 플러그인은 읽기·쓰기 권한을 함께 요청해서 쓰지 않는다 (tech-stack.md 1장).
 */
@CapacitorPlugin(
    name = "ContactReader",
    permissions = { @Permission(strings = { Manifest.permission.READ_CONTACTS }, alias = "contacts") }
)
public class ContactReaderPlugin extends Plugin {

    @PluginMethod
    public void pick(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_PICK, ContactsContract.Contacts.CONTENT_URI);
        startActivityForResult(call, intent, "pickResult");
    }

    @ActivityCallback
    private void pickResult(PluginCall call, ActivityResult result) {
        if (call == null) return;
        JSObject ret = new JSObject();
        Intent data = result.getData();
        if (result.getResultCode() != Activity.RESULT_OK || data == null || data.getData() == null) {
            ret.put("canceled", true);
            call.resolve(ret);
            return;
        }
        Uri uri = data.getData();
        String name = null;
        try (Cursor c = getContext().getContentResolver().query(
                uri, new String[] { ContactsContract.Contacts.DISPLAY_NAME_PRIMARY }, null, null, null)) {
            if (c != null && c.moveToFirst()) name = c.getString(0);
        } catch (Exception e) {
            call.reject("연락처를 읽지 못했어요: " + e.getMessage(), e);
            return;
        }
        ret.put("canceled", false);
        ret.put("name", name == null ? "" : name.trim());
        call.resolve(ret);
    }

    @PluginMethod
    public void list(PluginCall call) {
        if (getPermissionState("contacts") != PermissionState.GRANTED) {
            requestPermissionForAlias("contacts", call, "listPermission");
            return;
        }
        readAll(call);
    }

    @PermissionCallback
    private void listPermission(PluginCall call) {
        if (getPermissionState("contacts") != PermissionState.GRANTED) {
            call.reject("연락처 권한이 필요해요.", "DENIED");
            return;
        }
        readAll(call);
    }

    /** 이름과 회사명만 읽는다 */
    private void readAll(PluginCall call) {
        ContentResolver cr = getContext().getContentResolver();
        Map<Long, String> orgs = new HashMap<>();
        try (Cursor c = cr.query(
                ContactsContract.Data.CONTENT_URI,
                new String[] { ContactsContract.Data.CONTACT_ID, ContactsContract.CommonDataKinds.Organization.COMPANY },
                ContactsContract.Data.MIMETYPE + "=?",
                new String[] { ContactsContract.CommonDataKinds.Organization.CONTENT_ITEM_TYPE },
                null)) {
            while (c != null && c.moveToNext()) {
                String company = c.getString(1);
                if (company != null && !company.trim().isEmpty()) orgs.put(c.getLong(0), company.trim());
            }
        } catch (Exception ignored) {
            // 회사명을 못 읽어도 이름은 가져온다
        }

        JSArray list = new JSArray();
        try (Cursor c = cr.query(
                ContactsContract.Contacts.CONTENT_URI,
                new String[] { ContactsContract.Contacts._ID, ContactsContract.Contacts.DISPLAY_NAME_PRIMARY },
                null, null,
                ContactsContract.Contacts.DISPLAY_NAME_PRIMARY + " ASC")) {
            while (c != null && c.moveToNext()) {
                String name = c.getString(1);
                if (name == null || name.trim().isEmpty()) continue;
                long id = c.getLong(0);
                JSObject o = new JSObject();
                o.put("id", String.valueOf(id));
                o.put("name", name.trim());
                String org = orgs.get(id);
                o.put("org", org == null ? "" : org);
                list.put(o);
            }
        } catch (Exception e) {
            call.reject("연락처를 읽지 못했어요: " + e.getMessage(), e);
            return;
        }
        JSObject ret = new JSObject();
        ret.put("contacts", list);
        call.resolve(ret);
    }
}
