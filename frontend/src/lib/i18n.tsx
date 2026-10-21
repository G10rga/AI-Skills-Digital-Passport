import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "en" | "ka";

const dict = {
  en: {
    nav_verify: "Verify", nav_me: "My passport", nav_admin: "BTU admin",
    hero_title_1: "AI SKILLS", hero_title_2: "DIGITAL PASSPORT",
    hero_sub: "One permanent, verifiable record of every AI skill a BTU student earns — issued once, updated as a new version for every new skill, and impossible to fabricate: each version is fingerprinted with SHA-256, signed by BTU, and anchored on the blockchain.",
    open_my_passport: "Open my passport", verify_a_passport: "Verify a passport",
    how_it_works: "HOW BLOCKCHAIN VERIFICATION WORKS",
    sign_in: "Sign in with BTU", sign_in_sub: "Enter your BTU email. We send a 6-digit verification code — only a verified account can open a passport or request one.",
    email_ph: "name@btu.edu.ge", send_code: "Send verification code",
    code_ph: "6-digit code", verify_btn: "Verify and sign in",
    code_sent: "We sent a 6-digit code to your email. Check your inbox (and spam folder).",
    no_passport: "No passport is linked to this account yet.",
    request_passport: "Request my passport",
    request_sub: "We first search BTU's records for your email / student ID. If your data is there, your passport is generated immediately. If not, the request goes to BTU staff — you'll be notified here (and by email) when it's ready.",
    student_id_ph: "Student ID (e.g. BTU-T-0001)",
    request_btn: "Check and request passport",
    waiting_staff: "Your request is with BTU staff. You'll be notified when your passport is ready.",
    passport_ready: "Your passport is ready:",
    signed_in_as: "Signed in as", sign_out: "Sign out", hello: "Hello",
    my_requests: "My requests", request_skill: "Request a skill addition",
    notifications: "Notifications",
  },
  ka: {
    nav_verify: "გადამოწმება", nav_me: "ჩემი პასპორტი", nav_admin: "BTU ადმინი",
    hero_title_1: "AI უნარების", hero_title_2: "ციფრული პასპორტი",
    hero_sub: "BTU-ის სტუდენტის მიერ მიღებული ყველა AI უნარის ერთი მუდმივი, გადამოწმებადი ჩანაწერი — გაიცემა ერთხელ, ახლდება ახალი ვერსიით ყოველი ახალი უნარისთვის და მისი გაყალბება შეუძლებელია: თითოეული ვერსია აღიბეჭდება SHA-256 თითის ანაბეჭდით, ხელმოწერილია BTU-ის მიერ და ფიქსირდება ბლოკჩეინზე.",
    open_my_passport: "ჩემი პასპორტის გახსნა", verify_a_passport: "პასპორტის გადამოწმება",
    how_it_works: "როგორ მუშაობს ბლოკჩეინ-ვერიფიკაცია",
    sign_in: "BTU-ით შესვლა", sign_in_sub: "შეიყვანეთ თქვენი BTU ელფოსტა. გამოგიგზავნით 6-ნიშნა დამადასტურებელ კოდს — პასპორტის გახსნა ან მოთხოვნა მხოლოდ დადასტურებულ ანგარიშს შეუძლია.",
    email_ph: "name@btu.edu.ge", send_code: "კოდის გაგზავნა",
    code_ph: "6-ნიშნა კოდი", verify_btn: "დადასტურება და შესვლა",
    code_sent: "6-ნიშნა კოდი გამოგიგზავნეთ თქვენს ელფოსტაზე. შეამოწმეთ შემოსული (და სპამის) საქაღალდე.",
    no_passport: "ამ ანგარიშზე პასპორტი ჯერ არ არის მიბმული.",
    request_passport: "ჩემი პასპორტის მოთხოვნა",
    request_sub: "ჯერ ვეძებთ თქვენს ელფოსტას / სტუდენტის ID-ს BTU-ის ჩანაწერებში. თუ თქვენი მონაცემები მოიძებნა, პასპორტი მაშინვე გენერირდება. თუ არა, მოთხოვნა მიდის BTU-ის გუნდთან — შეგატყობინებთ აქ (და ელფოსტით), როცა მზად იქნება.",
    student_id_ph: "სტუდენტის ID (მაგ. BTU-T-0001)",
    request_btn: "შემოწმება და პასპორტის მოთხოვნა",
    waiting_staff: "თქვენი მოთხოვნა BTU-ის გუნდთანაა. შეგატყობინებთ, როცა პასპორტი მზად იქნება.",
    passport_ready: "თქვენი პასპორტი მზადაა:",
    signed_in_as: "შესული ხართ როგორც", sign_out: "გასვლა", hello: "გამარჯობა",
    my_requests: "ჩემი მოთხოვნები", request_skill: "უნარის დამატების მოთხოვნა",
    notifications: "შეტყობინებები",
  },
} as const;

export type TKey = keyof typeof dict.en;

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (k: TKey) => string }>({
  lang: "en", setLang: () => {}, t: (k) => dict.en[k],
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() =>
    (typeof window !== "undefined" && window.localStorage.getItem("btu-lang") as Lang) || "en");
  useEffect(() => { window.localStorage.setItem("btu-lang", lang); }, [lang]);
  return <Ctx.Provider value={{ lang, setLang, t: (k) => dict[lang][k] }}>{children}</Ctx.Provider>;
}

export const useLang = () => useContext(Ctx);
