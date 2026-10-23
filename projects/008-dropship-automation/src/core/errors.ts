/**
 * 공급처 어댑터가 발주 실패를 알릴 때 던지는 오류.
 * orderMayExist가 true면 공급처에 주문서가 만들어졌을 수도 있어(응답 불명, 일부만 주문 등)
 * 자동으로 다시 보내지 않고 사람이 확인하게 합니다.
 */
export class SupplierError extends Error {
  readonly code: string;
  readonly orderMayExist: boolean;
  constructor(code: string, message: string, orderMayExist = false) {
    super(message);
    this.code = code;
    this.orderMayExist = orderMayExist;
  }
}
