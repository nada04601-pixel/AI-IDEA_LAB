package kr.co.novalabs.maeumrecord;

import android.content.Context;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintManager;
import android.webkit.WebView;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * 현재 화면(WebView)을 안드로이드 기본 인쇄 화면으로 넘긴다.
 * 인쇄 화면에서 "PDF로 저장"을 고르면 리포트가 PDF 파일로 저장된다.
 * 웹의 window.print()와 같은 @media print 스타일이 적용되며, 인터넷이 필요 없다.
 */
@CapacitorPlugin(name = "WebPrint")
public class WebPrintPlugin extends Plugin {

    @PluginMethod
    public void print(PluginCall call) {
        final String name = call.getString("name", "마음기록 리포트");
        getActivity().runOnUiThread(() -> {
            try {
                PrintManager printManager = (PrintManager) getActivity().getSystemService(Context.PRINT_SERVICE);
                WebView webView = getBridge().getWebView();
                PrintDocumentAdapter adapter = webView.createPrintDocumentAdapter(name);
                PrintAttributes attributes = new PrintAttributes.Builder()
                        .setMediaSize(PrintAttributes.MediaSize.ISO_A4)
                        .build();
                printManager.print(name, adapter, attributes);
                call.resolve();
            } catch (Exception e) {
                call.reject("인쇄 화면을 열지 못했어요: " + e.getMessage(), e);
            }
        });
    }
}
