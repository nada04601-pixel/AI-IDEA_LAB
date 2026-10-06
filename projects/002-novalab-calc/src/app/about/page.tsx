import type { Metadata } from "next";
import { site } from "@/data/site";

export const metadata: Metadata = { title: "소개" };

export default function About() {
  return (
    <div className="w page">
      <h1>{site.name} 소개</h1>
      <p>{site.name}는 월급, 퇴직금, 대출처럼 생활에서 자주 마주치지만 계산이 헷갈리는 항목을 쉽게 확인할 수 있도록 만든 무료 계산기 모음입니다.</p>
      <h2>운영 원칙</h2>
      <p>계산 결과만 보여주지 않고 어떤 기준과 요율로 계산했는지 함께 설명합니다. 요율과 제도가 바뀌면 확인 일자를 표시하고 갱신합니다.</p>
      <h2>운영자</h2>
      <p>소프트웨어 개발 회사 노바랩스의 웹 개발자가 직접 만들고 운영합니다. 오류나 개선 의견은 <a href="/contact">문의 페이지</a>로 알려주세요.</p>
    </div>
  );
}
