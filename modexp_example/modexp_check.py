#!/usr/bin/env python3
"""modexp_check.py — 模幂与乘法阶的计算 / 独立核验脚本。

用法：
  compute --base A --exp E --mod M
  verify  --base A --exp E --mod M --claim C
  order   --base A --mod M

约定：
  - 所有结果以 JSON 打到 stdout；
  - 退出码：0 = 成功/核验接受；1 = 核验驳回；2 = 输入非法。
  - 仅使用 Python 标准库。
"""

import argparse
import json
import math
import sys


def emit(payload, code):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(code)


def check_common(base, mod):
    if mod <= 1:
        emit({"error": "modulus must be an integer > 1", "input": {"base": base, "mod": mod}}, 2)


def cmd_compute(args):
    check_common(args.base, args.mod)
    if args.exp < 0:
        emit({"error": "negative exponent is out of scope (modular inverse not supported)",
              "input": {"base": args.base, "exp": args.exp, "mod": args.mod}}, 2)
    result = pow(args.base, args.exp, args.mod)
    emit({
        "action": "compute",
        "input": {"base": args.base, "exp": args.exp, "mod": args.mod},
        "method": "python pow(base, exp, mod) (square-and-multiply)",
        "result": result,
    }, 0)


def cmd_verify(args):
    check_common(args.base, args.mod)
    if args.exp < 0:
        emit({"error": "negative exponent is out of scope",
              "input": {"base": args.base, "exp": args.exp, "mod": args.mod}}, 2)
    actual = pow(args.base, args.exp, args.mod)
    accepted = (actual == args.claim)
    payload = {
        "action": "verify",
        "input": {"base": args.base, "exp": args.exp, "mod": args.mod, "claim": args.claim},
        "method": "recompute independently with pow(base, exp, mod) and compare",
        "actual": actual,
        "accepted": accepted,
    }
    if not accepted:
        payload["reason"] = f"claimed {args.claim} but recomputation gives {actual}"
    emit(payload, 0 if accepted else 1)


def cmd_order(args):
    check_common(args.base, args.mod)
    if math.gcd(args.base, args.mod) != 1:
        emit({"error": "multiplicative order requires gcd(base, mod) = 1",
              "input": {"base": args.base, "mod": args.mod,
                        "gcd": math.gcd(args.base, args.mod)}}, 2)
    # 朴素枚举：教学脚本，适用于小模数；大模数应先分解 phi 再降阶。
    phi = sum(1 for k in range(1, args.mod + 1) if math.gcd(k, args.mod) == 1)
    value = args.base % args.mod
    for k in range(1, args.mod + 1):
        if value == 1:
            emit({
                "action": "order",
                "input": {"base": args.base, "mod": args.mod},
                "method": "enumerate powers base^1..base^phi (trial)",
                "phi_of_mod": phi,
                "order": k,
                "is_primitive_root": (k == phi),
            }, 0)
        value = (value * args.base) % args.mod
    # 理论上不可达（阶必整除 phi）
    emit({"error": "unreachable: order not found within phi iterations"}, 2)


def main():
    parser = argparse.ArgumentParser(description="Compute and verify modular exponentiation and multiplicative order.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_compute = sub.add_parser("compute", help="compute base^exp mod m")
    p_compute.add_argument("--base", type=int, required=True)
    p_compute.add_argument("--exp", type=int, required=True)
    p_compute.add_argument("--mod", type=int, required=True)
    p_compute.set_defaults(func=cmd_compute)

    p_verify = sub.add_parser("verify", help="independently verify a claimed base^exp mod m")
    p_verify.add_argument("--base", type=int, required=True)
    p_verify.add_argument("--exp", type=int, required=True)
    p_verify.add_argument("--mod", type=int, required=True)
    p_verify.add_argument("--claim", type=int, required=True)
    p_verify.set_defaults(func=cmd_verify)

    p_order = sub.add_parser("order", help="multiplicative order of base modulo m")
    p_order.add_argument("--base", type=int, required=True)
    p_order.add_argument("--mod", type=int, required=True)
    p_order.set_defaults(func=cmd_order)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
