import qrcode


_DEMO_PIX_KEY = "clickvagas@demo.invalid"


def _tlv(campo, valor):
    valor = str(valor)
    return f"{campo}{len(valor):02d}{valor}"


def gerar_payload_pix(valor, numero_vaga):
    """Monta um payload Pix de demonstração com valor e chave fictícia."""
    merchant_account = _tlv("00", "br.gov.bcb.pix") + _tlv(
        "01", _DEMO_PIX_KEY
    )
    additional_data = _tlv("05", f"CV{int(numero_vaga):02d}")
    campos = (
        _tlv("00", "01")
        + _tlv("01", "11")
        + _tlv("26", merchant_account)
        + _tlv("52", "0000")
        + _tlv("53", "986")
        + _tlv("54", f"{valor:.2f}")
        + _tlv("58", "BR")
        + _tlv("59", "CLICK VAGAS")
        + _tlv("60", "BRASIL")
        + _tlv("62", additional_data)
        + "6304"
    )
    return campos + f"{_crc16_ccitt(campos):04X}"


def _crc16_ccitt(texto):
    crc = 0xFFFF
    for byte in texto.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def gerar_matriz_qr(payload):
    codigo = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=2,
    )
    codigo.add_data(payload)
    codigo.make(fit=True)
    return codigo.get_matrix()
