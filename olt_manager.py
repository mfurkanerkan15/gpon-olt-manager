import re
import time
from datetime import datetime

DANGEROUS_CHARS_REGEX = re.compile(r"[\r\n;&|`$<>]")

def validate_sn(sn: str) -> str:
    """ONT Seri Numarası doğrulaması (Sadece alfanumerik, 4-32 karakter)."""
    if not sn or not isinstance(sn, str):
        raise ValueError("Seri numarası (SN) boş olamaz.")
    sn = sn.strip()
    if DANGEROUS_CHARS_REGEX.search(sn):
        raise ValueError("Seri numarası zararlı özel karakterler içeremez!")
    if not re.match(r"^[A-Za-z0-9]{4,32}$", sn):
        raise ValueError(f"Geçersiz Seri Numarası formatı ({sn}). Sadece 4-32 karakter uzunluğunda harf ve rakam girilmelidir.")
    return sn

def validate_fsp(fsp: str) -> tuple[int, int, int]:
    """Frame/Slot/Port (F/S/P) formatı doğrulaması (Örnek: 0/1/7)."""
    if not fsp or not isinstance(fsp, str):
        raise ValueError("F/S/P bilgisi boş olamaz.")
    fsp = fsp.strip()
    if DANGEROUS_CHARS_REGEX.search(fsp):
        raise ValueError("F/S/P bilgisi zararlı özel karakterler içeremez!")
    match = re.match(r"^(\d+)/(\d+)/(\d+)$", fsp)
    if not match:
        raise ValueError(f"Geçersiz F/S/P formatı: '{fsp}'. Format 'Frame/Slot/Port' (örnek: 0/2/14) olmalıdır.")
    frame, slot, port = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if frame < 0 or frame > 99 or slot < 0 or slot > 99 or port < 0 or port > 99:
        raise ValueError(f"F/S/P değerleri geçerli aralıkta değil: {fsp}")
    return frame, slot, port

def validate_int_range(val, name: str, min_val: int, max_val: int) -> int:
    """Tamsayı aralık doğrulaması."""
    try:
        val_int = int(val)
    except (ValueError, TypeError):
        raise ValueError(f"{name} geçerli bir tamsayı olmalıdır.")
    if val_int < min_val or val_int > max_val:
        raise ValueError(f"{name} ({val_int}) {min_val} ile {max_val} arasında olmalıdır.")
    return val_int


class HuaweiOLT:
    """
    Huawei OLT (MA5680T) Simülasyon / Mock Yönetim Sınıfı.
    Arayüz testi ve açık kaynak sunum için gerçekçi OLT CLI yanıtları ve akışları simüle eder.
    """

    def __init__(self, host, username, password, port=22, protocol="ssh"):
        if not host or not isinstance(host, str):
            raise ValueError("Host/IP adresi boş olamaz.")
        self.host = host.strip()
        self.username = str(username).strip()
        self.password = str(password)
        self.port = validate_int_range(port, "Port", 1, 65535)
        
        protocol = str(protocol).lower().strip()
        if protocol not in ("ssh", "telnet"):
            raise ValueError(f"Desteklenmeyen protokol: {protocol}. Yalnızca 'ssh' veya 'telnet' seçilebilir.")
        self.protocol = protocol
        self.is_connected = False
        
        # Simülasyon modu için dinamik modem havuzu
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S+03:00")
        self.mock_autofind_onts = [
            {
                "number": "1",
                "fsp": "0/1/7",
                "sn": "485754434F0AB99E",
                "equipment_id": "GW020",
                "version": "ONT050201B",
                "time": now_str
            },
            {
                "number": "2",
                "fsp": "0/2/14",
                "sn": "5A544547DCE1E885",
                "equipment_id": "ZXHN F660",
                "version": "ONT0201A",
                "time": now_str
            }
        ]

    def connect(self):
        """OLT bağlantısını simüle eder."""
        time.sleep(0.5)
        self.is_connected = True
        return "MA5680T(config)#"

    def disconnect(self):
        """OLT bağlantısını sonlandırır."""
        self.is_connected = False

    def command(self, cmd):
        """CLI komut yanıtını simüle eder."""
        return f"MA5680T(config)# {cmd}\nCommand success"

    def find_onts(self):
        """
        Kayıt bekleyen (autofind) modemleri bulur ve listeler (Mock).
        """
        time.sleep(0.5)
        return [dict(ont) for ont in self.mock_autofind_onts]

    def register_ont(self, fsp, sn, line_profile, srv_profile, vlan, gemport=1, user_vlan=1):
        """
        ONT kaydeder, ONT ID'yi tespit eder ve service-port vlan ayarını yapar (Mock).
        Tüm parametreler güvenlik doğrulamalarından geçirilir.
        """
        frame, slot, port = validate_fsp(fsp)
        sn = validate_sn(sn)
        line_profile = validate_int_range(line_profile, "Line Profile ID", 1, 4096)
        srv_profile = validate_int_range(srv_profile, "Service Profile ID", 1, 4096)
        vlan = validate_int_range(vlan, "VLAN ID", 1, 4094)
        gemport = validate_int_range(gemport, "Gemport ID", 1, 128)
        user_vlan = validate_int_range(user_vlan, "User VLAN", 1, 4094)
        fsp_clean = f"{frame}/{slot}/{port}"

        time.sleep(0.8)
        
        # Kaydedilen modemi autofind listesinden düşür
        self.mock_autofind_onts = [ont for ont in self.mock_autofind_onts if ont.get("sn") != sn]
        ont_id = "7"
        
        logs = [
            f"[SIMÜLASYON MODU] OLT bağlantısı aktif ({self.host}).",
            f"> interface gpon {frame}/{slot}",
            f"MA5680T(config-if-gpon-{frame}/{slot})#",
            f"> ont confirm {port} sn-auth {sn} omci ont-lineprofile-id {line_profile} ont-srvprofile-id {srv_profile}",
            f"Add ONT successfully, ONT ID is {ont_id}",
            f"> display ont info by-sn {sn}",
            f"-----------------------------------------------------------",
            f"F/S/P             : {fsp_clean}",
            f"ONT-ID            : {ont_id}",
            f"Control flag      : active",
            f"Run state         : online",
            f"Config state      : normal",
            f"Match state       : match",
            f"-----------------------------------------------------------",
            f"[OK] ONT ID tespit edildi: {ont_id}",
            f"> quit",
            f"MA5680T(config)#",
            f"> service-port vlan {vlan} gpon {frame}/{slot}/{port} ont {ont_id} gemport {gemport} multi-service user-vlan {user_vlan} tag-transform translate",
            f"Command success",
            f"[OK] ONT kaydı ve {vlan} VLAN service-port tanımı başarıyla tamamlandı."
        ]
        return "\n".join(logs)

    def delete_ont_by_sn(self, sn):
        """
        ONT kaydını ve bağlı olduğu service-port'ları seri numarasına göre siler (Mock).
        """
        sn = validate_sn(sn)
        
        time.sleep(0.8)

        # Silinen modemi simülasyonda tekrar autofind listesine ekle
        already_exists = any(ont.get("sn") == sn for ont in self.mock_autofind_onts)
        if not already_exists:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S+03:00")
            self.mock_autofind_onts.append({
                "number": str(len(self.mock_autofind_onts) + 1),
                "fsp": "0/1/7",
                "sn": sn,
                "equipment_id": "RESTORED-ONT",
                "version": "V1.0",
                "time": now_str
            })

        logs = [
            f"[SIMÜLASYON MODU] Modem Silme Akışı Başlatıldı. Seri No: {sn}",
            f"> display ont info by-sn {sn}",
            f"-----------------------------------------------------------",
            f"F/S/P             : 0/1/7",
            f"ONT-ID            : 2",
            f"Control flag      : active",
            f"Run state         : online",
            f"Config state      : normal",
            f"Match state       : match",
            f"-----------------------------------------------------------",
            f"[OK] ONT Bulundu: Konum: 0/1/7, ONT ID: 2",
            f"> display service-port port 0/1/7 ont 2",
            f"  ----------------------------------------------------------------------------",
            f"  INDEX V-ID M-V-ID C-PORT F/S/P   ONT   GEMPORT S-VLAN C-VLAN FLOW-GP TYPE STATE",
            f"  ----------------------------------------------------------------------------",
            f"     15 2031     -      - 0/1/7      2         1   2031      -       - eth  up",
            f"  ----------------------------------------------------------------------------",
            f"[OK] Silinecek 1 adet service-port bulundu: [15]",
            f"> undo service-port 15",
            f"Command success",
            f"> interface gpon 0/1",
            f"MA5680T(config-if-gpon-0/1)#",
            f"> ont delete 7 2",
            f"Command success",
            f"> quit",
            f"MA5680T(config)#",
            f"[OK] ONT kaydı ve ilgili tüm portlar başarıyla silindi."
        ]
        return "\n".join(logs)