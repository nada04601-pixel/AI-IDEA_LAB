import Link from "next/link";

export default function NotFound() {
  return (
    <div className="w page">
      <h1>페이지를 찾을 수 없습니다</h1>
      <p className="lead">주소가 바뀌었거나 삭제된 페이지입니다.</p>
      <p><Link className="btn" href="/">계산기 목록으로</Link></p>
    </div>
  );
}
