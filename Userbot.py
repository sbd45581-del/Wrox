"""
Telegram Kanal/Grup Koruma Botu (Userbot)
------------------------------------------------
Kurucusu olduğunuz kanal/gruplarda:

  1) Siz DIŞINDA biri video/gif/video-note/FOTOĞRAF paylaştığında
     mesajı otomatik olarak siler.
  2) İçinde YASAKLI kelime/ifade (küfür dahil) geçen mesajları (kim
     atarsa atsın) otomatik siler.
  3) İçinde RAKAM geçen (telefon numarası, çalıntı kart numarası, vb.)
     mesajları otomatik siler. BLOCK_ALL_DIGITS=True iken rakam içeren
     hiçbir mesaj kalmaz; False yapılırsa sadece telefon/kart benzeri
     kalıplar hedeflenir.
  4) Siz DIŞINDA biri bir üyeyi GRUPTAN/KANALDAN ATARSA (kick/ban),
     üyenin banını kaldırıp otomatik olarak geri ekler.
  5) Siz DIŞINDA biri KANAL/GRUP PROFİL FOTOĞRAFINI değiştirdiğinde,
     fotoğrafı otomatik kaldırır.
  6) Siz DIŞINDA biri KANAL/GRUP İSMİNİ değiştirdiğinde, ismi otomatik
     olarak eski (doğru) haline geri çevirir. Bu koruma hem kanal/
     süper-grup hem de normal (basic) gruplar için çalışır.
  7) KANAL/GRUP AÇIKLAMASI (about/description) değiştiğinde -kim
     değiştirirse değiştirsin- otomatik olarak eski haline geri
     çevirir. (Telegram, about değişikliklerinde "kim değiştirdi"
     bilgisini normal event ile vermediği için bu kontrol periyodik
     yoklama ile yapılır ve HERKESİN -senin dahil- yaptığı
     değişiklikleri geri alır. Açıklamayı gerçekten değiştirmek
     istersen DESIRED_OVERRIDE kısmını kullan ya da botu geçici
     olarak durdur.)
  8) Siz DIŞINDA biri ÇIKARTMA (sticker) paylaşırsa, mesajı otomatik
     siler. BLOCK_STICKERS=False yapılırsa bu koruma kapanır.
  9) Siz DIŞINDA biri mesajında EMOJİ kullanırsa, mesajı otomatik
     siler. BLOCK_EMOJI=False yapılırsa bu koruma kapanır.

KURULUM:
1) pip install telethon
2) https://my.telegram.org adresinden API_ID ve API_HASH al
3) Aşağıdaki API_ID / API_HASH alanlarını doldur
4) python video_silici_bot.py komutuyla çalıştır
   (ilk seferde telefon numaranı ve Telegram'dan gelen kodu isteyecek)

NOT:
- Bu script "userbot" mantığıyla çalışır, yani senin kendi hesabınla
  giriş yapar (Bot API token'ı değil). Telegram, hesaplarda otomasyon
  kullanımını sınırlayabilir/kısıtlayabilir; makul limitler içinde
  kullanmaya dikkat et.
- Script sadece SENİN "kurucu" (creator) olduğun kanal/supergroup/
  gruplarda işlem yapar, başka yerlerde hiçbir şeye dokunmaz.
- Üye geri ekleme özelliği (madde 4), kişinin gizlilik ayarlarına göre
  bazen başarısız olabilir (örn. "kimler beni gruba ekleyebilir" kısıtlı
  ise); bu durumda konsola hata basılır ama bot çökmez.
- Açıklama (about) koruması periyodik yoklama ile çalışır (madde 7'deki
  notu oku); yani "gruptaki açıklamayı değiştiremesinler" isteği zaten
  bu mekanizma ile karşılanıyor - kim değiştirirse değiştirsin en geç
  DESCRIPTION_CHECK_INTERVAL saniye içinde eski haline döner.
"""

import asyncio
import re
import unicodedata
from telethon import TelegramClient, events
from telethon.errors import ChatAdminRequiredError
from telethon.tl.types import InputChatPhotoEmpty, Channel, ChatBannedRights
from telethon.tl.functions.channels import (
    EditPhotoRequest,
    EditTitleRequest,
    GetFullChannelRequest,
    EditBannedRequest,
    InviteToChannelRequest,
)
from telethon.tl.functions.messages import (
    EditChatAboutRequest,
    EditChatTitleRequest,
    EditChatPhotoRequest,
    GetFullChatRequest,
    AddChatUserRequest,
)

# ==================== AYARLAR ====================
API_ID = 33724739                              # my.telegram.org'dan alınan api_id (int)
API_HASH = "1a620b776b0ecabb53eb24c0834080e5"  # my.telegram.org'dan alınan api_hash (str)
SESSION_NAME = "video_silici_session"

# Kendi video/fotoğraf/sticker/emoji paylaşımlarını da silsin mi?
# False = kendi paylaşımların (ve mesajların) kalsın
DELETE_OWN_VIDEOS_TOO = False

# Siz DIŞINDA biri ÇIKARTMA (sticker) atarsa otomatik silinsin mi?
BLOCK_STICKERS = True

# Mesaj içinde EMOJİ geçiyorsa otomatik silinsin mi? (kim atarsa atsın,
# DELETE_OWN_VIDEOS_TOO ile aynı istisna mantığı geçerlidir)
BLOCK_EMOJI = True

# İçinde geçmesi YASAK kelime/ifadeler (büyük/küçük harf ve Türkçe İ/I
# varyasyonları önemsiz - hepsi normalize edilip karşılaştırılır).
# Tek kelimeler (boşluksuz) kelime sınırına göre eşleşir (ör. "cc" içeren
# "account" kelimesini YAKALAMAZ). Boşluk/özel karakter içerenler ise
# düz metin olarak aranır.
BANNED_WORDS = [
    "child porn",
    "cc",
    "10$",
    "10$ child porn",
    # --- Küfür / hakaret filtresi ---
    # İstediğin kadar kelime ekleyebilirsin, liste büyük/küçük harf ve
    # Türkçe İ/I farkı gözetmeden çalışır.
    "amk",
    "amına koyayım",
    "siktir",
    "orospu çocuğu",
    "piç",
    "yarrak",
    "amcık",
    "göt oğlanı",
    "ibne",
    "Allahını sikim",
    "allahını sikim",
    "AMK",
    "OROSPU ÇOCU",
    "orospu çocu",
    "alahını sikim",
    "ananı sikim",
    "gavat",
    "Amk",
    "CC",
    "Cc",
    "porno",
    "sex",
    "10$ CHİLD PORN",
    "çocuk porno",
    "ananı öldürüm"
]

# Mesajda RAKAM (0-9) geçiyorsa mesajı tamamen sil (telefon numarası,
# çalıntı kart numarası, fiyat vb. her türlü sayısal içerik dahil).
# True yaparsan rakam içeren HİÇBİR mesaj gönderilemez (kimden gelirse gelsin).
BLOCK_ALL_DIGITS = True

# BLOCK_ALL_DIGITS False yapılırsa, bunun yerine sadece aşağıdaki daha
# spesifik kalıplar (telefon numarası / kart numarası benzeri diziler)
# aranıp silinir.
PHONE_NUMBER_PATTERN = re.compile(r'(\+?\d[\d\-\s]{7,14}\d)')
CARD_NUMBER_PATTERN = re.compile(r'(?:\d[ \-]?){13,19}')

# Metin içinde emoji tespiti için unicode aralıkları (yaygın emoji blokları)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # semboller, piktogramlar, ek emoji blokları
    "\U00002600-\U000027BF"  # çeşitli semboller / dingbats (☀️ ✂️ vb.)
    "\U0001F1E6-\U0001F1FF"  # bayrak harfleri (regional indicator)
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\U00002190-\U000021FF"  # oklar
    "\U00002300-\U000023FF"  # teknik semboller (⏰ ⌚ vb.)
    "\U0000FE0F"              # variation selector (emoji sunum işareti)
    "\U0000200D"              # zero-width joiner (birleşik emojiler)
    "]+",
    flags=re.UNICODE,
)

# Seni DIŞINDA biri bir üyeyi gruptan/kanaldan atarsa (kick/ban), üyeyi
# otomatik olarak geri ekleme koruması aktif olsun mu?
PROTECT_AGAINST_KICKS = True

# Açıklama (about) değişikliğini kaç saniyede bir kontrol etsin
DESCRIPTION_CHECK_INTERVAL = 30

# İstersen belirli bir kanal/grup için sabit bir açıklama/isim zorla.
# Boş bırakırsan, script başlarken kanaldaki mevcut değeri "doğru" kabul eder.
# Örnek: {-1001234567890: {"title": "Resmi Kanalım", "about": "Açıklama metni"}}
DESIRED_OVERRIDE = {}
# ===================================================

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# chat_id -> (is_creator: bool, checked_at: float)
_creator_cache = {}
# "Kurucu değilim" sonucunu ne kadar süre cache'de tutalım (saniye).
# Bu süre dolunca tekrar kontrol edilir - böylece sonradan sana devredilen
# / admin/kurucu yapıldığın kanallar restart beklemeden algılanır.
CREATOR_CACHE_TTL_NOT_CREATOR = 60
# "Kurucuyum" sonucunu daha uzun süre güvenip cache'leyebiliriz.
CREATOR_CACHE_TTL_CREATOR = 600

# Yeni kurucu olduğun / sonradan eklenen kanal-grupları yakalamak için
# tüm diyalogları kaç saniyede bir yeniden tarasın
DIALOG_RESCAN_INTERVAL = 60

_me_id = None
# chat_id -> {"title": str, "about": str, "entity": entity}
_baseline = {}


def normalize_text(text: str) -> str:
    """
    Türkçe İ/I harflerini ve diğer unicode varyasyonlarını güvenli şekilde
    küçük harfe çevirir. Python'un varsayılan str.lower() metodu Türkçe
    büyük 'İ' harfini normal 'i' yerine noktalı bileşik bir karaktere
    çevirdiği için (locale farkı), banned-word eşleşmesi kaçabiliyordu.
    Bu fonksiyon önce Türkiye'ye özgü harfleri ASCII eşdeğerine çevirir,
    sonra unicode normalizasyonu + lower() uygular.
    """
    if not text:
        return ""
    # Türkçe büyük/küçük İ, I, ı, i -> düz ascii i/i eşlemesi
    text = text.replace("İ", "i").replace("I", "i").replace("ı", "i")
    # Kalan aksanlı/özel karakterleri ayrıştırıp (NFKD) ve harf dışı
    # birleşik işaretleri (combining marks) temizle
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


_banned_patterns = []
for w in BANNED_WORDS:
    wl = normalize_text(w)
    if wl.isalnum():
        _banned_patterns.append(("word", re.compile(r"\b" + re.escape(wl) + r"\b")))
    else:
        _banned_patterns.append(("substr", wl))


def contains_banned_word(text: str) -> bool:
    if not text:
        return False
    low = normalize_text(text)
    for kind, pat in _banned_patterns:
        if kind == "word":
            if pat.search(low):
                return True
        else:
            if pat in low:
                return True
    return False


def contains_digit(text: str) -> bool:
    """Metinde herhangi bir rakam (0-9) var mı?"""
    if not text:
        return False
    return bool(re.search(r"\d", text))


def contains_phone_or_card(text: str) -> bool:
    """Metinde telefon numarası veya (çalıntı) kart numarası benzeri bir dizi var mı?"""
    if not text:
        return False
    if PHONE_NUMBER_PATTERN.search(text):
        return True
    if CARD_NUMBER_PATTERN.search(text):
        return True
    return False


def contains_emoji(text: str) -> bool:
    """Metinde emoji (veya emoji sunum/birleştirme işareti) var mı?"""
    if not text:
        return False
    return bool(EMOJI_PATTERN.search(text))


def is_sticker_message(event) -> bool:
    """Mesaj bir çıkartma (sticker) mı?"""
    return bool(getattr(event, "sticker", None))


def is_media_to_delete(event) -> bool:
    """Mesaj video, video note (yuvarlak video), gif veya fotoğraf mı?"""
    if event.video or event.gif or event.photo:
        return True
    if event.message and event.message.video_note:
        return True
    return False


async def am_i_creator(chat_id: int, force: bool = False) -> bool:
    """
    Bu kanalda/grupta ben kurucu muyum? (TTL'li cache)
    - "Kurucuyum" sonucu CREATOR_CACHE_TTL_CREATOR saniye boyunca güvenilir.
    - "Kurucu değilim" sonucu ise sadece CREATOR_CACHE_TTL_NOT_CREATOR saniye
      cache'lenir; süre dolunca tekrar kontrol edilir. Böylece sonradan
      sahipliği sana devredilen ya da kurucu yapıldığın kanal/gruplar
      botu yeniden başlatmana gerek kalmadan algılanır.
    """
    now = asyncio.get_event_loop().time()
    cached = _creator_cache.get(chat_id)
    if cached is not None and not force:
        result, checked_at = cached
        ttl = CREATOR_CACHE_TTL_CREATOR if result else CREATOR_CACHE_TTL_NOT_CREATOR
        if now - checked_at < ttl:
            return result

    try:
        perms = await client.get_permissions(chat_id, _me_id)
        result = bool(getattr(perms, "is_creator", False))
    except ChatAdminRequiredError:
        result = False
    except Exception:
        result = False

    was_creator = cached[0] if cached else False
    _creator_cache[chat_id] = (result, now)

    # Az önce kurucu olmadığın ama şimdi kurucu olduğun ortaya çıktıysa,
    # bu kanal/grubu hemen baseline'a ekle.
    if result and not was_creator:
        try:
            await add_or_refresh_baseline(chat_id)
            print(f"[YENİ KURUCULUK ALGILANDI] Kanal/Grup: {chat_id} -> baseline'a eklendi")
        except Exception as e:
            print(f"[HATA] Yeni kurucu baseline eklenemedi ({chat_id}) -> {e}")

    return result


async def get_about(entity) -> str:
    """Kanal/grup açıklamasını (about) getirir."""
    try:
        if isinstance(entity, Channel):
            full = await client(GetFullChannelRequest(entity))
        else:
            full = await client(GetFullChatRequest(entity.id))
        return full.full_chat.about or ""
    except Exception:
        return None


def get_photo_id(entity):
    """Entity'nin mevcut profil fotoğrafının id'sini döndürür (foto yoksa None)."""
    photo = getattr(entity, "photo", None)
    return getattr(photo, "photo_id", None)


async def revert_title(entity, new_title: str):
    """Hem kanal/süper-grup hem de normal (basic) grup için ismi geri çevirir."""
    if isinstance(entity, Channel):
        await client(EditTitleRequest(channel=entity, title=new_title))
    else:
        await client(EditChatTitleRequest(chat_id=entity.id, title=new_title))


async def revert_photo(entity):
    """Hem kanal/süper-grup hem de normal (basic) grup için profil fotoğrafını kaldırır."""
    if isinstance(entity, Channel):
        await client(EditPhotoRequest(channel=entity, photo=InputChatPhotoEmpty()))
    else:
        await client(EditChatPhotoRequest(chat_id=entity.id, photo=InputChatPhotoEmpty()))


async def revert_about(entity, old_about: str):
    """Hem kanal/süper-grup hem de normal (basic) grup için açıklamayı geri çevirir."""
    await client(EditChatAboutRequest(peer=entity, about=old_about))


async def add_or_refresh_baseline(chat_id: int):
    """Tek bir kanal/grup için baseline kaydını oluşturur/günceller (zaten varsa dokunmaz)."""
    if chat_id in _baseline:
        return
    entity = await client.get_entity(chat_id)
    dialog_title = getattr(entity, "title", None)
    override = DESIRED_OVERRIDE.get(chat_id, {})
    title = override.get("title", dialog_title)
    about = override.get("about")
    if about is None:
        about = await get_about(entity)
    _baseline[chat_id] = {
        "title": title,
        "about": about or "",
        "entity": entity,
        "photo_id": get_photo_id(entity),
    }
    print(f"[BASELINE] '{title}' (id={chat_id}) kaydedildi")


async def build_baseline():
    """Kurucu olduğun her kanal/grup için başlangıç isim+açıklama değerini kaydeder."""
    async for dialog in client.iter_dialogs():
        if not (dialog.is_channel or dialog.is_group):
            continue
        chat_id = dialog.id
        if not await am_i_creator(chat_id, force=True):
            continue
        entity = dialog.entity
        override = DESIRED_OVERRIDE.get(chat_id, {})
        title = override.get("title", dialog.title)
        about = override.get("about")
        if about is None:
            about = await get_about(entity)
        _baseline[chat_id] = {
            "title": title,
            "about": about or "",
            "entity": entity,
            "photo_id": get_photo_id(entity),
        }
        print(f"[BASELINE] '{title}' (id={chat_id}) kaydedildi")


async def dialog_rescanner():
    """
    Periyodik olarak TÜM diyalogları tarar. Bu, botu yeniden başlatmadan:
    - sonradan eklendiğin / kurucu yapıldığın kanal-grupları,
    - sahipliği sonradan sana devredilen kanal-grupları
    baseline'a dahil etmek içindir.
    """
    while True:
        await asyncio.sleep(DIALOG_RESCAN_INTERVAL)
        try:
            async for dialog in client.iter_dialogs():
                if not (dialog.is_channel or dialog.is_group):
                    continue
                chat_id = dialog.id
                # force=True: cache'e güvenme, gerçek yetkiyi kontrol et
                is_creator = await am_i_creator(chat_id, force=True)
                if is_creator and chat_id not in _baseline:
                    await add_or_refresh_baseline(chat_id)
        except Exception as e:
            print(f"[HATA] Diyalog taraması başarısız -> {e}")


async def profile_watcher():
    """
    Açıklama, isim ve profil fotoğrafı değişikliklerini periyodik olarak
    kontrol edip geri alır. Bu, ChatAction event'lerine ek bir GÜVENCE
    katmanıdır: bazı hesap/kanal tiplerinde Telegram isim/foto
    değişikliklerini normal event olarak iletmeyebiliyor (bkz. koddaki
    DEBUG logu). Bu fonksiyon sayesinde event kaçsa bile en geç
    DESCRIPTION_CHECK_INTERVAL saniye içinde değişiklik geri alınır.
    """
    while True:
        await asyncio.sleep(DESCRIPTION_CHECK_INTERVAL)
        for chat_id, base in list(_baseline.items()):
            entity = base.get("entity")
            if not entity:
                continue

            # Güncel entity'yi tazele (foto/isim güncel halini görmek için)
            try:
                fresh_entity = await client.get_entity(chat_id)
            except Exception as e:
                print(f"[HATA] Entity yenilenemedi ({chat_id}) -> {e}")
                fresh_entity = entity

            # --- Açıklama kontrolü ---
            current_about = await get_about(entity)
            if current_about is not None and current_about != base.get("about", ""):
                try:
                    await revert_about(entity, base["about"])
                    print(f"[AÇIKLAMA GERİ ALINDI] Kanal/Grup: {chat_id}")
                except Exception as e:
                    print(f"[HATA] Açıklama geri alınamadı ({chat_id}) -> {e}")

            # --- İsim kontrolü (periyodik yedek) ---
            current_title = getattr(fresh_entity, "title", None)
            baseline_title = base.get("title")
            if baseline_title is not None and current_title and current_title != baseline_title:
                try:
                    await revert_title(fresh_entity, baseline_title)
                    print(f"[İSİM GERİ ALINDI - periyodik] Kanal/Grup: {chat_id} -> '{baseline_title}'")
                except Exception as e:
                    print(f"[HATA] İsim geri alınamadı - periyodik ({chat_id}) -> {e}")

            # --- Profil fotoğrafı kontrolü (periyodik yedek) ---
            current_photo_id = get_photo_id(fresh_entity)
            baseline_photo_id = base.get("photo_id")
            if current_photo_id != baseline_photo_id:
                try:
                    await revert_photo(fresh_entity)
                    # Foto kaldırıldığı için enforce edilen "doğru" durum artık "fotosuz"
                    base["photo_id"] = None
                    print(f"[FOTO KALDIRILDI - periyodik] Kanal/Grup: {chat_id}")
                except Exception as e:
                    print(f"[HATA] Foto kaldırılamadı - periyodik ({chat_id}) -> {e}")


@client.on(events.NewMessage())
async def on_new_message(event):
    if not (event.is_channel or event.is_group):
        return
    if not await am_i_creator(event.chat_id):
        return

    sender_id = event.sender_id
    is_owner_msg = sender_id == _me_id

    # 1) Yasaklı kelime/ifade (küfür dahil) kontrolü - kimden gelirse gelsin silinir
    if contains_banned_word(event.raw_text):
        try:
            await event.delete()
            print(f"[YASAKLI İÇERİK/KÜFÜR SİLİNDİ] Kanal/Grup: {event.chat_id} | Gönderen: {sender_id}")
        except Exception as e:
            print(f"[HATA] Yasaklı mesaj silinemedi -> {e}")
        return

    # 2) Rakam kontrolü - telefon numarası, çalıntı kart numarası, fiyat vb.
    #    BLOCK_ALL_DIGITS=True ise rakam geçen HİÇBİR mesaj kalmaz.
    if BLOCK_ALL_DIGITS:
        if contains_digit(event.raw_text):
            try:
                await event.delete()
                print(f"[RAKAM İÇEREN MESAJ SİLİNDİ] Kanal/Grup: {event.chat_id} | Gönderen: {sender_id}")
            except Exception as e:
                print(f"[HATA] Rakamlı mesaj silinemedi -> {e}")
            return
    else:
        if contains_phone_or_card(event.raw_text):
            try:
                await event.delete()
                print(f"[TELEFON/KART NUMARASI SİLİNDİ] Kanal/Grup: {event.chat_id} | Gönderen: {sender_id}")
            except Exception as e:
                print(f"[HATA] Telefon/kart mesajı silinemedi -> {e}")
            return

    # 3) Emoji kontrolü - mesaj metninde emoji geçiyorsa silinir
    if BLOCK_EMOJI and not (is_owner_msg and not DELETE_OWN_VIDEOS_TOO):
        if contains_emoji(event.raw_text):
            try:
                await event.delete()
                print(f"[EMOJİ İÇEREN MESAJ SİLİNDİ] Kanal/Grup: {event.chat_id} | Gönderen: {sender_id}")
            except Exception as e:
                print(f"[HATA] Emojili mesaj silinemedi -> {e}")
            return

    # 4) Çıkartma (sticker) kontrolü
    if BLOCK_STICKERS and is_sticker_message(event):
        if not (is_owner_msg and not DELETE_OWN_VIDEOS_TOO):
            try:
                await event.delete()
                print(f"[ÇIKARTMA SİLİNDİ] Kanal/Grup: {event.chat_id} | Gönderen: {sender_id}")
            except Exception as e:
                print(f"[HATA] Çıkartma silinemedi -> {e}")
            return

    # 5) Video / foto / gif kontrolü
    if not is_media_to_delete(event):
        return
    if is_owner_msg and not DELETE_OWN_VIDEOS_TOO:
        return

    try:
        await event.delete()
        kind = "Foto" if event.photo else ("Gif" if event.gif else "Video")
        print(f"[{kind} SİLİNDİ] Kanal/Grup: {event.chat_id} | Gönderen: {sender_id}")
    except Exception as e:
        print(f"[HATA] Kanal/Grup: {event.chat_id} silinemedi -> {e}")


@client.on(events.ChatAction())
async def on_chat_action(event):
    try:
        await _handle_chat_action(event)
    except Exception as e:
        print(f"[HATA] on_chat_action işlenemedi -> {e}")


async def _handle_chat_action(event):
    # DEBUG: Bu satır her ChatAction event'inde çalışır - isim/foto
    # değişikliklerinin bota gerçekten ulaşıp ulaşmadığını görmek için.
    # Sorun devam ederse konsol çıktısını kontrol et: bu log hiç
    # görünmüyorsa Telegram bu event'i bu hesaba iletmiyor demektir
    # (örn. büyük/yayın kanallarında bazı service-message türleri
    # normal kullanıcı hesaplarına düşmeyebilir).
    print(f"[DEBUG ChatAction] chat={event.chat_id} new_title={event.new_title!r} "
          f"new_photo={bool(event.new_photo)} action_msg={bool(event.action_message)}")

    if not (event.is_channel or event.is_group):
        return
    if not await am_i_creator(event.chat_id):
        print(f"[DEBUG] {event.chat_id} için kurucu değilsin (cache) -> koruma uygulanmadı")
        return

    actor_id = event.action_message.sender_id if event.action_message else None
    is_owner_action = actor_id == _me_id

    # --- Biri (sen dışında) bir üyeyi ATTI/BANLADI mı? ---
    # NOT: telethon sürümüne göre 'user_banned' attribute'u bulunmayabilir,
    # bu yüzden getattr ile güvenli okuyoruz (yoksa False kabul edilir).
    was_kicked = getattr(event, "user_kicked", False)
    was_banned = getattr(event, "user_banned", False)
    if PROTECT_AGAINST_KICKS and (was_kicked or was_banned) and not is_owner_action:
        try:
            kicked_users = await event.get_users()
            chat = await event.get_chat()
            for u in kicked_users:
                try:
                    if isinstance(chat, Channel):
                        # Önce banı kaldır (aksi halde tekrar davet edilemez)
                        await client(EditBannedRequest(
                            channel=chat,
                            participant=u,
                            banned_rights=ChatBannedRights(until_date=0, view_messages=None),
                        ))
                        await client(InviteToChannelRequest(chat, [u]))
                    else:
                        await client(AddChatUserRequest(chat.id, u.id, fwd_limit=10))
                    print(f"[ÜYE GERİ EKLENDİ] {getattr(u, 'id', u)} -> Kanal/Grup: {event.chat_id} | Atan: {actor_id}")
                except Exception as e:
                    print(f"[HATA] Üye geri eklenemedi ({getattr(u, 'id', u)}) -> {e}")
        except Exception as e:
            print(f"[HATA] Atılan üye bilgisi alınamadı ({event.chat_id}) -> {e}")

    # --- Profil fotoğrafı değişti mi? ---
    if event.new_photo and is_owner_action:
        # Sen değiştirdiysen bunu yeni "doğru" foto olarak kaydet
        if event.chat_id in _baseline:
            try:
                fresh_entity = await client.get_entity(event.chat_id)
                _baseline[event.chat_id]["photo_id"] = get_photo_id(fresh_entity)
            except Exception:
                pass
    if event.new_photo and not is_owner_action:
        try:
            chat = await event.get_chat()
            await revert_photo(chat)
            if event.chat_id in _baseline:
                _baseline[event.chat_id]["photo_id"] = None
            print(f"[FOTO KALDIRILDI] Kanal/Grup: {event.chat_id} | Değiştiren: {actor_id}")
        except Exception as e:
            print(f"[HATA] Foto kaldırılamadı ({event.chat_id}) -> {e}")

    # --- İsim (başlık) değişti mi? (kanal, süper-grup veya normal grup) ---
    if event.new_title:
        if is_owner_action:
            # Sen değiştirdiysen bunu yeni "doğru" isim olarak kaydet
            if event.chat_id in _baseline:
                _baseline[event.chat_id]["title"] = event.new_title
        else:
            base = _baseline.get(event.chat_id)
            if base and base.get("title") is not None:
                try:
                    chat = await event.get_chat()
                    await revert_title(chat, base["title"])
                    print(f"[İSİM GERİ ALINDI] Kanal/Grup: {event.chat_id} -> '{base['title']}' | Değiştiren: {actor_id}")
                except Exception as e:
                    print(f"[HATA] İsim geri alınamadı ({event.chat_id}) -> {e}")
            try:
                if event.action_message:
                    await event.action_message.delete()
            except Exception:
                pass


async def main():
    global _me_id
    await client.start()
    me = await client.get_me()
    _me_id = me.id
    print(f"Giriş yapıldı: {me.first_name} (id={me.id})")

    print("Kurucu olduğun kanal/gruplar taranıyor, isim/açıklama kaydediliyor...")
    await build_baseline()

    asyncio.create_task(profile_watcher())
    asyncio.create_task(dialog_rescanner())

    print("Bot çalışıyor: video/foto/gif/sticker/emoji, yasaklı kelime, rakam, isim ve açıklama koruması aktif.")
    print(f"(Yeni kurucu olunan kanal/gruplar her {DIALOG_RESCAN_INTERVAL} saniyede bir otomatik taranacak)")
    print("Durdurmak için CTRL+C")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())

