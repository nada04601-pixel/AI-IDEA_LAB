import type { Metadata } from "next";
import { site } from "@/data/site";

export const metadata: Metadata = { title: "문의" };

export default function Contact() {
  return (
    <div className="w page">
      <h1>문의</h1>
      <p>계산 오류 제보, 기능 제안, 제휴 문의는 아래 이메일로 보내주세요. 영업일 기준 며칠 안에 답변드립니다.</p>
      <p><a className="btn" href={`mailto:${site.email}`}>{site.email}</a></p>
      <p className="note">계산 결과가 실제와 다르다면 입력한 값과 기대한 금액을 함께 알려주시면 확인이 빠릅니다.</p>
    </div>
  );
}
