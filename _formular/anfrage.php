<?php
// DUCT TAPE – Booking-Anfrageformular
// Liegt auf dem IONOS-Webspace unter https://formular.ducttape.berlin/anfrage.php
// Nimmt das Formular von ducttape.berlin/anfrage.html (bzw. /en/enquiry.html) an,
// schickt die Anfrage als Mail an booking@ und leitet auf die Danke-Seite weiter.
// Es wird nichts gespeichert: keine Datenbank, keine Logdatei.

const EMPFAENGER = 'booking@ducttape.berlin';
const ABSENDER   = 'info@ducttape.berlin';   // muss ein Postfach bei IONOS sein
const SITE       = 'https://ducttape.berlin';

$lang  = (($_POST['lang'] ?? '') === 'en') ? 'en' : 'de';
$danke = SITE . ($lang === 'en' ? '/en/thank-you.html' : '/danke.html');
$form  = SITE . ($lang === 'en' ? '/en/enquiry.html' : '/anfrage.html');

function weiter($url) { header('Location: ' . $url, true, 303); exit; }
function feld($k, $max = 300) {
  $v = trim((string)($_POST[$k] ?? ''));
  $v = str_replace(["\r\n", "\r"], "\n", $v);
  return mb_substr($v, 0, $max, 'UTF-8');
}
function zeile($v) { return trim(preg_replace('/[\r\n\t]+/', ' ', $v)); }

if ($_SERVER['REQUEST_METHOD'] !== 'POST') weiter($form);

// Nur Anfragen von der eigenen Website annehmen
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin !== '' && !in_array($origin, [SITE, 'https://www.ducttape.berlin'], true)) weiter($form . '?fehler=1');

// Spamschutz: verstecktes Feld muss leer sein, Formular nicht schneller als 3 Sekunden ausgefüllt
if (feld('website') !== '') weiter($danke);
$t = (int)feld('t', 20);
if ($t > 0 && time() - $t < 3) weiter($danke);

$name     = zeile(feld('name', 120));
$email    = zeile(feld('email', 160));
$programm = zeile(feld('programm', 80));
if ($name === '' || $programm === '' || !filter_var($email, FILTER_VALIDATE_EMAIL) || feld('einwilligung', 5) !== 'ja') {
  weiter($form . '?fehler=1');
}

$acts = ['' => 'Noch offen', 'kollektiv' => 'Das ganze Kollektiv', 'emi' => 'EMI', 'symba' => 'Symba', 'magda' => 'Magda von Pfeffer'];
$act  = $acts[feld('act', 20)] ?? 'Noch offen';
$datum = feld('datum', 20);
if (preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $datum, $m)) $datum = "$m[3].$m[2].$m[1]";

$telefon = zeile(feld('telefon', 60));
$abschnitte = [
  'Anfrage' => [
    'Programm'       => $programm,
    'Act'            => $act,
    'Datum'          => zeile($datum),
    'Ort / Location' => zeile(feld('ort', 160)),
    'Gäste'          => zeile(feld('gaeste', 10)),
    'Anlass'         => zeile(feld('anlass', 160)),
  ],
  'Kontakt' => [
    'Name'                 => $name,
    'E-Mail'               => $email,
    'Telefon'              => $telefon,
    'Firma / Organisation' => zeile(feld('firma', 160)),
  ],
  'Herkunft' => [
    'Gefunden über' => zeile(feld('gefunden', 60)),
    'Quelle'        => zeile(feld('quelle', 300)),
    'Sprache'       => strtoupper($lang),
  ],
];
$nachricht = feld('nachricht', 5000);
$betreff = 'Booking-Anfrage: ' . $programm . ' – ' . $name . ($datum !== '' ? ' (' . $datum . ')' : '');

// Textfassung (für Mailprogramme ohne HTML)
$text = "NEUE BOOKING-ANFRAGE über ducttape.berlin\n";
foreach ($abschnitte as $titel => $felder) {
  $text .= "\n" . mb_strtoupper($titel, 'UTF-8') . "\n";
  foreach ($felder as $k => $v) if ($v !== '') $text .= '  ' . $k . ': ' . $v . "\n";
  if ($titel === 'Anfrage' && $nachricht !== '') $text .= "\nNACHRICHT\n" . $nachricht . "\n";
}
$text .= "\nAntworten geht direkt an " . $email . ".\n";

// HTML-Fassung
function h($v) { return htmlspecialchars($v, ENT_QUOTES, 'UTF-8'); }
$antwort = 'mailto:' . rawurlencode($email) . '?subject=' . rawurlencode('Re: ' . $betreff);
$html  = '<!doctype html><html><body style="margin:0;padding:0;background:#f2f2f2;">';
$html .= '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2f2f2;padding:24px 12px;"><tr><td align="center">';
$html .= '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:10px;overflow:hidden;font-family:-apple-system,Helvetica,Arial,sans-serif;color:#111;">';
$html .= '<tr><td style="background:#0b0b0b;padding:20px 24px;"><div style="color:#e8c33a;font-size:12px;font-weight:700;letter-spacing:2px;">NEUE BOOKING-ANFRAGE</div>'
       . '<div style="color:#ffffff;font-size:22px;font-weight:700;margin-top:6px;">' . h($programm) . '</div>'
       . '<div style="color:#bbbbbb;font-size:15px;margin-top:4px;">' . h($name) . ($datum !== '' ? ' · ' . h($datum) : '') . '</div></td></tr>';
foreach ($abschnitte as $titel => $felder) {
  $leise = ($titel === 'Herkunft');
  $html .= '<tr><td style="padding:20px 24px 4px;"><div style="font-size:12px;font-weight:700;letter-spacing:1.5px;color:#888;text-transform:uppercase;">' . h($titel) . '</div></td></tr>';
  $html .= '<tr><td style="padding:0 24px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">';
  foreach ($felder as $k => $v) {
    if ($v === '') continue;
    $wert = h($v);
    if ($k === 'E-Mail')  $wert = '<a href="mailto:' . h($v) . '" style="color:#111;">' . h($v) . '</a>';
    if ($k === 'Telefon') $wert = '<a href="tel:' . h(preg_replace('/[^\d+]/', '', $v)) . '" style="color:#111;">' . h($v) . '</a>';
    $groesse = $leise ? '13px' : '15px';
    $html .= '<tr><td style="padding:7px 0;border-bottom:1px solid #eee;width:38%;vertical-align:top;font-size:' . $groesse . ';color:#777;">' . h($k) . '</td>'
           . '<td style="padding:7px 0;border-bottom:1px solid #eee;vertical-align:top;font-size:' . $groesse . ';color:' . ($leise ? '#777' : '#111') . ';' . ($leise ? '' : 'font-weight:600;') . 'word-break:break-word;">' . $wert . '</td></tr>';
  }
  $html .= '</table></td></tr>';
  if ($titel === 'Anfrage' && $nachricht !== '') {
    $html .= '<tr><td style="padding:16px 24px 0;"><div style="font-size:12px;font-weight:700;letter-spacing:1.5px;color:#888;">NACHRICHT</div>'
           . '<div style="margin-top:8px;padding:14px 16px;background:#faf6e3;border-left:4px solid #e8c33a;border-radius:4px;font-size:15px;line-height:1.5;">' . nl2br(h($nachricht)) . '</div></td></tr>';
  }
}
$html .= '<tr><td style="padding:24px;" align="left"><a href="' . h($antwort) . '" style="display:inline-block;background:#e8c33a;color:#0b0b0b;font-weight:700;font-size:15px;text-decoration:none;padding:12px 22px;border-radius:999px;">' . h($name) . ' antworten</a></td></tr>';
$html .= '</table></td></tr></table></body></html>';

$grenze = 'dt-' . bin2hex(random_bytes(8));
$inhalt = "--$grenze\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n" . chunk_split(base64_encode($text))
        . "--$grenze\r\nContent-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n" . chunk_split(base64_encode($html))
        . "--$grenze--\r\n";
$header  = implode("\r\n", [
  'From: ' . mb_encode_mimeheader('DUCT TAPE Website', 'UTF-8') . ' <' . ABSENDER . '>',
  'Reply-To: ' . mb_encode_mimeheader($name, 'UTF-8') . ' <' . $email . '>',
  'MIME-Version: 1.0',
  'Content-Type: multipart/alternative; boundary="' . $grenze . '"',
]);

$ok = mail(EMPFAENGER, mb_encode_mimeheader($betreff, 'UTF-8'), $inhalt, $header, '-f' . ABSENDER);
weiter($ok ? $danke : $form . '?fehler=1');
