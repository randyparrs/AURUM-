# { "Depends": "py-genlayer:1j12s63yfjpva9ik2xgnffgrs6v44y1f52jvj9w7xvdn7qckd379" }

import json
from genlayer import *

class AurumCore(gl.Contract):

    owner:    Address
    treasury: u256

    fee_token_scanner:     u256
    fee_wallet_insights:   u256
    fee_smart_money_radar: u256
    fee_gem_finder:        u256

    total_token_scans:     u256
    total_wallet_analyses: u256
    total_radar_refreshes: u256
    total_gem_searches:    u256

    user_history:       DynArray[str]
    authorized_modules: DynArray[str]

    def __init__(self, owner_address: str):
        if isinstance(owner_address, int):
            self.owner = Address("0x" + format(owner_address, '040x'))
        else:
            self.owner = Address(owner_address)
        self.treasury = u256(0)

        self.fee_token_scanner     = u256(1_000_000_000_000_000_000)
        self.fee_wallet_insights   = u256(1_000_000_000_000_000_000)
        self.fee_smart_money_radar = u256(300_000_000_000_000_000)
        self.fee_gem_finder        = u256(1_000_000_000_000_000_000)

        self.total_token_scans     = u256(0)
        self.total_wallet_analyses = u256(0)
        self.total_radar_refreshes = u256(0)
        self.total_gem_searches    = u256(0)

    @gl.public.write
    def set_fee(self, module: str, amount_wei: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        valid = ["token_scanner", "wallet_insights", "smart_money_radar", "gem_finder"]
        assert module in valid, "Invalid module"
        amount = u256(int(amount_wei))
        if module == "token_scanner":
            self.fee_token_scanner = amount
        elif module == "wallet_insights":
            self.fee_wallet_insights = amount
        elif module == "smart_money_radar":
            self.fee_smart_money_radar = amount
        elif module == "gem_finder":
            self.fee_gem_finder = amount

    @gl.public.write
    def withdraw_treasury(self, amount_wei: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        amount = u256(int(amount_wei))
        assert int(amount) <= int(self.treasury), "Insufficient treasury"
        self.treasury = u256(int(self.treasury) - int(amount))

    @gl.public.write
    def transfer_ownership(self, new_owner: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        if isinstance(new_owner, int):
            self.owner = Address("0x" + format(new_owner, '040x'))
        else:
            self.owner = Address(new_owner)

    @gl.public.write
    def add_authorized_module(self, module_address: str) -> None:
        assert gl.message.sender_address == self.owner, "Not owner"
        if module_address not in self.authorized_modules:
            self.authorized_modules.append(module_address)

    @gl.public.write
    def collect_fee(self, module: str, user_wallet: str) -> None:
        caller = str(gl.message.sender_address)
        assert caller in self.authorized_modules, "Not authorized module"
        assert int(gl.message.value) > 0, "No fee sent"

        self.treasury = u256(int(self.treasury) + int(gl.message.value))

        if module == "token_scanner":
            self.total_token_scans = u256(int(self.total_token_scans) + 1)
        elif module == "wallet_insights":
            self.total_wallet_analyses = u256(int(self.total_wallet_analyses) + 1)
        elif module == "smart_money_radar":
            self.total_radar_refreshes = u256(int(self.total_radar_refreshes) + 1)
        elif module == "gem_finder":
            self.total_gem_searches = u256(int(self.total_gem_searches) + 1)

        prefix = user_wallet + ":"
        raw = ""
        for i in range(len(self.user_history)):
            if self.user_history[i].startswith(prefix):
                raw = self.user_history[i][len(prefix):]
                break
        try:
            history = json.loads(raw) if raw else []
        except Exception:
            history = []
        history.append({"module": module})
        if len(history) > 50:
            history = history[-50:]
        entry = prefix + json.dumps(history)
        found = False
        for i in range(len(self.user_history)):
            if self.user_history[i].startswith(prefix):
                self.user_history[i] = entry
                found = True
                break
        if not found:
            self.user_history.append(entry)

    @gl.public.view
    def get_fees(self) -> str:
        return json.dumps({
            "token_scanner":     str(int(self.fee_token_scanner)),
            "wallet_insights":   str(int(self.fee_wallet_insights)),
            "smart_money_radar": str(int(self.fee_smart_money_radar)),
            "gem_finder":        str(int(self.fee_gem_finder)),
        }, sort_keys=True)

    @gl.public.view
    def get_treasury_balance(self) -> str:
        return json.dumps({
            "treasury_wei": str(int(self.treasury)),
        }, sort_keys=True)

    @gl.public.view
    def get_global_stats(self) -> str:
        total = (
            int(self.total_token_scans) +
            int(self.total_wallet_analyses) +
            int(self.total_radar_refreshes) +
            int(self.total_gem_searches)
        )
        return json.dumps({
            "total_analyses":    total,
            "token_scans":       int(self.total_token_scans),
            "wallet_analyses":   int(self.total_wallet_analyses),
            "radar_refreshes":   int(self.total_radar_refreshes),
            "gem_searches":      int(self.total_gem_searches),
        }, sort_keys=True)

    @gl.public.view
    def get_user_history(self, wallet: str) -> str:
        prefix = wallet + ":"
        for i in range(len(self.user_history)):
            if self.user_history[i].startswith(prefix):
                return self.user_history[i][len(prefix):]
        return "[]"

    @gl.public.view
    def get_authorized_modules(self) -> str:
        return json.dumps(list(self.authorized_modules))

    @gl.public.view
    def get_owner(self) -> str:
        return str(self.owner)

    @gl.public.view
    def get_summary(self) -> str:
        total = (
            int(self.total_token_scans) +
            int(self.total_wallet_analyses) +
            int(self.total_radar_refreshes) +
            int(self.total_gem_searches)
        )
        return json.dumps({
            "owner":              str(self.owner),
            "treasury_wei":       str(int(self.treasury)),
            "total_analyses":     total,
            "authorized_modules": len(self.authorized_modules),
        }, sort_keys=True)
