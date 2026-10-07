/* 공통 스크립트: 모바일 메뉴, 숫자 입력 콤마 처리, 포맷 함수 */
(function () {
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('site-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  // data-money 속성이 있는 입력칸은 입력 중 천 단위 콤마 표시
  document.querySelectorAll('input[data-money]').forEach(function (input) {
    input.setAttribute('inputmode', 'numeric');
    input.addEventListener('input', function () {
      var digits = input.value.replace(/[^0-9]/g, '');
      input.value = digits ? Number(digits).toLocaleString('ko-KR') : '';
    });
  });
})();

window.Calc = {
  /** 콤마 등을 제거하고 숫자로 변환 (빈 값이면 NaN) */
  num: function (el) {
    var v = (typeof el === 'string' ? document.getElementById(el).value : el.value).replace(/,/g, '').trim();
    return v === '' ? NaN : Number(v);
  },
  won: function (n) {
    return Math.round(n).toLocaleString('ko-KR') + '원';
  },
  fmt: function (n, digits) {
    return Number(n).toLocaleString('ko-KR', { maximumFractionDigits: digits == null ? 2 : digits });
  },
  radio: function (name) {
    var el = document.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : null;
  },
  set: function (id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  },
  /** 폼의 모든 입력 변화에 fn을 연결하고 최초 1회 실행 */
  bind: function (formId, fn) {
    var form = document.getElementById(formId);
    form.addEventListener('input', fn);
    form.addEventListener('change', fn);
    form.addEventListener('submit', function (e) { e.preventDefault(); fn(); });
    fn();
  },
  /** 'YYYY-MM-DD' 를 로컬 날짜로 변환 */
  parseDate: function (s) {
    if (!s) return null;
    var p = s.split('-').map(Number);
    return new Date(p[0], p[1] - 1, p[2]);
  },
  toISO: function (d) {
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return d.getFullYear() + '-' + m + '-' + day;
  },
  dayDiff: function (a, b) {
    var utcA = Date.UTC(a.getFullYear(), a.getMonth(), a.getDate());
    var utcB = Date.UTC(b.getFullYear(), b.getMonth(), b.getDate());
    return Math.round((utcB - utcA) / 86400000);
  },
  weekday: function (d) {
    return ['일', '월', '화', '수', '목', '금', '토'][d.getDay()] + '요일';
  }
};
