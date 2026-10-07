package kr.co.novalabs.maeumjangbu;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Rect;
import android.util.Base64;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions;

/**
 * 사진 → 글자 (Google ML Kit 한국어 텍스트 인식, 휴대폰 안에서 처리) — tech-stack.md 3장
 *
 * 이 플러그인은 "이미지 → 줄 단위 글자 + 위치"까지만 한다.
 * 이름·금액을 나누는 규칙은 웹 코드(src/lib/ocrParse.ts)에 두어 테스트한다.
 * 모델은 앱에 포함(bundled)되어 인터넷 없이 동작한다. 사진은 저장하거나 보내지 않는다.
 */
@CapacitorPlugin(name = "TextRecognition")
public class TextRecognitionPlugin extends Plugin {

    private TextRecognizer recognizer;

    private TextRecognizer recognizer() {
        if (recognizer == null) {
            recognizer = TextRecognition.getClient(new KoreanTextRecognizerOptions.Builder().build());
        }
        return recognizer;
    }

    @PluginMethod
    public void recognize(PluginCall call) {
        String base64 = call.getString("base64");
        if (base64 == null || base64.isEmpty()) {
            call.reject("사진이 없어요.");
            return;
        }
        Bitmap bitmap;
        try {
            int comma = base64.indexOf(',');
            byte[] bytes = Base64.decode(comma >= 0 ? base64.substring(comma + 1) : base64, Base64.DEFAULT);
            bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        } catch (Exception e) {
            call.reject("사진을 열지 못했어요: " + e.getMessage(), e);
            return;
        }
        if (bitmap == null) {
            call.reject("사진을 열지 못했어요.");
            return;
        }
        final int width = bitmap.getWidth();
        final int height = bitmap.getHeight();
        InputImage image = InputImage.fromBitmap(bitmap, 0);
        recognizer()
            .process(image)
            .addOnSuccessListener(text -> {
                JSArray lines = new JSArray();
                for (Text.TextBlock block : text.getTextBlocks()) {
                    for (Text.Line line : block.getLines()) {
                        Rect r = line.getBoundingBox();
                        if (r == null) continue;
                        JSObject o = new JSObject();
                        o.put("text", line.getText());
                        o.put("left", r.left);
                        o.put("top", r.top);
                        o.put("right", r.right);
                        o.put("bottom", r.bottom);
                        lines.put(o);
                    }
                }
                JSObject ret = new JSObject();
                ret.put("width", width);
                ret.put("height", height);
                ret.put("lines", lines);
                call.resolve(ret);
            })
            .addOnFailureListener(e -> call.reject("글자를 읽지 못했어요: " + e.getMessage(), e));
    }

    @Override
    protected void handleOnDestroy() {
        if (recognizer != null) recognizer.close();
        super.handleOnDestroy();
    }
}
