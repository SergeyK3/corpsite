/**
 * PIF-2B — Electronic Personnel Intake Demo Prototype
 * Pure client-side wizard; no backend.
 */

(function () {
  "use strict";

  const STEPS = [
    { id: "welcome", label: "Начало", title: "Анкета нового сотрудника", showProgress: false },
    { id: "basic", label: "Основные сведения", title: "Основные сведения", stepNum: 1 },
    { id: "contact", label: "Контакты", title: "Контактные данные", stepNum: 2 },
    { id: "document", label: "Документы", title: "Документ, удостоверяющий личность", stepNum: 3 },
    { id: "education", label: "Образование", title: "Образование", stepNum: 4 },
    { id: "training", label: "Повышение квалификации", title: "Повышение квалификации", stepNum: 5 },
    { id: "employment", label: "Опыт работы", title: "Трудовая деятельность", stepNum: 6 },
    { id: "family", label: "Семья", title: "Семья", stepNum: 7 },
    { id: "military", label: "Воинский учёт", title: "Воинский учёт", stepNum: 8 },
    { id: "additional", label: "Дополнительно", title: "Дополнительные сведения", stepNum: 9 },
    { id: "review", label: "Проверка", title: "Проверка заполнения", stepNum: 10 },
    { id: "success", label: "Готово", title: "Анкета отправлена", showProgress: false },
  ];

  const TOTAL_FORM_STEPS = 11;

  let currentIndex = 0;
  let cardIdCounter = 1;
  let submissionRef = "";

  function mockFile(name, type) {
    try {
      return new File(["demo"], name, { type: type || "image/png" });
    } catch (_) {
      return { name: name, size: 4, type: type || "image/png" };
    }
  }

  function fillDemoData() {
    Object.assign(state, {
      lastName: "Касымова",
      firstName: "Айгуль",
      middleName: "Ерлановна",
      iin: "900101350123",
      birthDate: "1990-01-01",
      gender: "female",
      birthPlace: "г. Алматы",
      citizenship: "Казахстан",
      nationality: "Казах",
      maritalStatus: "married",
      photoFile: mockFile("photo-demo.png", "image/png"),
      phone: "+7 701 123 45 67",
      phoneAlt: "",
      email: "aigul.kasymova@example.kz",
      regAddress: "г. Алматы, ул. Абая, д. 10, кв. 25",
      liveAddress: "г. Алматы, ул. Абая, д. 10, кв. 25",
      sameAddress: true,
      docType: "id_kz",
      docNumber: "012345678",
      docIssuer: "МВД РК",
      docIssueDate: "2020-05-15",
      docExpiry: "2030-05-14",
      docFile: mockFile("udostoverenie-demo.pdf", "application/pdf"),
      education: [
        {
          id: "edu-1",
          level: "higher",
          institution: "КазНУ им. аль-Фараби",
          country: "Казахстан",
          year: "2012",
          specialty: "Экономика",
          qualification: "Экономист",
          diplomaNum: "AB 1234567",
          diplomaDate: "2012-06-20",
          diplomaFile: mockFile("diplom-demo.pdf", "application/pdf"),
        },
      ],
      trainingMode: "none",
      training: [],
      employmentMode: "has",
      employment: [
        {
          id: "emp-1",
          org: 'ТОО "Бизнес Партнёр"',
          position: "Бухгалтер",
          startDate: "2015-03-01",
          endDate: "2024-12-31",
          current: false,
          reason: "Переход в новую организацию",
          location: "г. Алматы",
          docFile: null,
        },
      ],
      spouseMode: "fill",
      spouseName: "Касымов Ерлан Бекенович",
      spouseBirth: "1988-07-12",
      spouseWork: 'АО "Алматы Энерго"',
      spousePhone: "+7 702 987 65 43",
      childrenMode: "has",
      children: [{ name: "Касымова Амина", birth: "2015-09-03" }],
      emergencyName: "Касымов Ерлан Бекенович",
      emergencyRelation: "Супруг",
      emergencyPhone: "+7 702 987 65 43",
      militaryMode: "na",
      militaryDuty: "",
      militaryRank: "",
      militaryCategory: "",
      militaryProfile: "",
      militaryDocType: "",
      militaryDocNum: "",
      militaryDocDate: "",
      militaryDocFile: null,
      additionalMode: "none",
      languages: [],
      hasLicense: "no",
      licenseCategories: "",
      licenseExpiry: "",
      academicDegree: "",
      academicTitle: "",
      awards: [],
      otherInfo: "",
      confirmAccuracy: true,
      confirmConsent: true,
    });

    const btn = $("#btnDemoAutofill");
    if (btn) {
      btn.textContent = "Демо-данные загружены";
      btn.classList.add("demo-autofill-btn--done");
      btn.disabled = true;
    }

    renderStep(currentIndex);
    updateProgressUI();
  }

  const state = {
    lastName: "",
    firstName: "",
    middleName: "",
    iin: "",
    birthDate: "",
    gender: "",
    birthPlace: "",
    citizenship: "Казахстан",
    nationality: "",
    maritalStatus: "",
    photoFile: null,
    phone: "",
    phoneAlt: "",
    email: "",
    regAddress: "",
    liveAddress: "",
    sameAddress: false,
    docType: "",
    docNumber: "",
    docIssuer: "",
    docIssueDate: "",
    docExpiry: "",
    docFile: null,
    education: [{ id: "edu-1", level: "", institution: "", country: "Казахстан", year: "", specialty: "", qualification: "", diplomaNum: "", diplomaDate: "", diplomaFile: null }],
    trainingMode: "none",
    training: [],
    employmentMode: "has",
    employment: [{ id: "emp-1", org: "", position: "", startDate: "", endDate: "", current: false, reason: "", location: "", docFile: null }],
    spouseMode: "na",
    spouseName: "",
    spouseBirth: "",
    spouseWork: "",
    spousePhone: "",
    childrenMode: "none",
    children: [],
    emergencyName: "",
    emergencyRelation: "",
    emergencyPhone: "",
    militaryMode: "na",
    militaryDuty: "",
    militaryRank: "",
    militaryCategory: "",
    militaryProfile: "",
    militaryDocType: "",
    militaryDocNum: "",
    militaryDocDate: "",
    militaryDocFile: null,
    additionalMode: "none",
    languages: [],
    hasLicense: "no",
    licenseCategories: "",
    licenseExpiry: "",
    academicDegree: "",
    academicTitle: "",
    awards: [],
    otherInfo: "",
    confirmAccuracy: false,
    confirmConsent: false,
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const sidebar = $("#sidebar");
  const mobileStepper = $("#mobileStepper");
  const panelHeader = $("#panelHeader");
  const panelBody = $("#panelBody");
  const panelFooter = $("#panelFooter");

  function nextCardId(prefix) {
    cardIdCounter += 1;
    return `${prefix}-${cardIdCounter}`;
  }

  function esc(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fieldHtml({ id, label, required, type = "text", hint, value, options, full, rows, accept, checked }) {
    const req = required ? '<span class="req">*</span>' : "";
    const fullClass = full ? " form-field--full" : "";
    let input = "";

    if (type === "select") {
      const opts = (options || [])
        .map((o) => `<option value="${esc(o.value)}"${value === o.value ? " selected" : ""}>${esc(o.label)}</option>`)
        .join("");
      input = `<select class="form-select" id="${id}" data-field="${id}">${opts}</select>`;
    } else if (type === "textarea") {
      input = `<textarea class="form-textarea" id="${id}" data-field="${id}" rows="${rows || 3}">${esc(value || "")}</textarea>`;
    } else if (type === "radio") {
      input = `<div class="form-radio-group">${(options || [])
        .map(
          (o) =>
            `<label class="form-radio"><input type="radio" name="${id}" value="${esc(o.value)}" data-field="${id}"${value === o.value ? " checked" : ""} /> ${esc(o.label)}</label>`
        )
        .join("")}</div>`;
    } else if (type === "file") {
      const name = value ? esc(value) : "";
      const has = value ? " form-file--has-file" : "";
      input = `<div class="form-file${has}" data-file-wrap="${id}">
        <input type="file" id="${id}" data-field="${id}" accept="${accept || ""}" />
        <div class="form-file__label">${hint || "Нажмите, чтобы выбрать файл"}</div>
        <div class="form-file__name">${name}</div>
      </div>`;
    } else if (type === "checkbox") {
      input = `<label class="form-checkbox"><input type="checkbox" id="${id}" data-field="${id}"${checked ? " checked" : ""} /> <span>${label}${req}</span></label>`;
      return `<div class="form-field${fullClass}">${input}${hint ? `<span class="form-hint">${esc(hint)}</span>` : ""}<div class="form-error" data-error="${id}"></div></div>`;
    } else {
      input = `<input class="form-input" type="${type}" id="${id}" data-field="${id}" value="${esc(value || "")}" />`;
    }

    return `<div class="form-field${fullClass}">
      ${type !== "checkbox" ? `<label class="form-label" for="${id}">${esc(label)}${req}</label>` : ""}
      ${input}
      ${hint && type !== "file" && type !== "checkbox" ? `<span class="form-hint">${esc(hint)}</span>` : ""}
      <div class="form-error" data-error="${id}"></div>
    </div>`;
  }

  function bindFields(root) {
    root.querySelectorAll("[data-field]").forEach((el) => {
      const key = el.dataset.field;
      const handler = () => {
        if (el.type === "checkbox") state[key] = el.checked;
        else if (el.type === "file") {
          state[key] = el.files[0] || null;
          const wrap = el.closest("[data-file-wrap]");
          if (wrap) {
            wrap.classList.toggle("form-file--has-file", !!el.files[0]);
            const nameEl = wrap.querySelector(".form-file__name");
            if (nameEl) nameEl.textContent = el.files[0] ? el.files[0].name : "";
          }
        } else if (el.type === "radio") {
          if (el.checked) state[key] = el.value;
        } else state[key] = el.value;

        if (key === "sameAddress" && state.sameAddress) {
          state.liveAddress = state.regAddress;
          const live = root.querySelector("#liveAddress");
          if (live) {
            live.value = state.regAddress;
            live.disabled = true;
          }
        } else if (key === "sameAddress" && !state.sameAddress) {
          const live = root.querySelector("#liveAddress");
          if (live) live.disabled = false;
        } else if (key === "regAddress" && state.sameAddress) {
          state.liveAddress = state.regAddress;
          const live = root.querySelector("#liveAddress");
          if (live) live.value = state.regAddress;
        }

        updateProgressUI();
      };
      el.addEventListener("input", handler);
      el.addEventListener("change", handler);
    });

    root.querySelectorAll(".form-file").forEach((wrap) => {
      wrap.addEventListener("click", () => {
        const input = wrap.querySelector("input[type=file]");
        if (input) input.click();
      });
    });
  }

  function setError(fieldId, msg) {
    const el = document.querySelector(`[data-error="${fieldId}"]`);
    const input = document.getElementById(fieldId);
    if (el) el.textContent = msg || "";
    if (input && input.classList) {
      input.classList.toggle("form-input--error", !!msg);
      input.classList.toggle("form-select--error", !!msg);
      input.classList.toggle("form-textarea--error", !!msg);
    }
  }

  function clearErrors(root) {
    root.querySelectorAll(".form-error").forEach((e) => (e.textContent = ""));
    root.querySelectorAll(".form-input--error, .form-select--error, .form-textarea--error").forEach((e) => {
      e.classList.remove("form-input--error", "form-select--error", "form-textarea--error");
    });
  }

  function validateIin(v) {
    return /^\d{12}$/.test((v || "").replace(/\s/g, ""));
  }

  function validatePhone(v) {
    const digits = (v || "").replace(/\D/g, "");
    return digits.length >= 10;
  }

  function validateEmail(v) {
    if (!v) return true;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
  }

  function validateDateOrder(start, end) {
    if (!start || !end) return true;
    return new Date(end) >= new Date(start);
  }

  function validateStep(index) {
    const step = STEPS[index];
    clearErrors(panelBody);
    let ok = true;
    let firstBad = null;

    const fail = (id, msg) => {
      setError(id, msg);
      ok = false;
      if (!firstBad) firstBad = document.getElementById(id);
    };

    if (step.id === "basic") {
      if (!state.lastName.trim()) fail("lastName", "Укажите фамилию");
      if (!state.firstName.trim()) fail("firstName", "Укажите имя");
      if (!validateIin(state.iin)) fail("iin", "ИИН должен содержать 12 цифр");
      if (!state.birthDate) fail("birthDate", "Укажите дату рождения");
      if (!state.gender) fail("gender", "Выберите пол");
      if (!state.citizenship) fail("citizenship", "Укажите гражданство");
      if (!state.maritalStatus) fail("maritalStatus", "Укажите семейное положение");
      if (!state.photoFile) fail("photoFile", "Прикрепите фото");
    }

    if (step.id === "contact") {
      if (!validatePhone(state.phone)) fail("phone", "Укажите корректный телефон");
      if (!validateEmail(state.email)) fail("email", "Проверьте адрес email");
      if (!state.regAddress.trim()) fail("regAddress", "Укажите адрес регистрации");
      if (!state.liveAddress.trim()) fail("liveAddress", "Укажите адрес проживания");
    }

    if (step.id === "document") {
      if (!state.docType) fail("docType", "Выберите тип документа");
      if (!state.docNumber.trim()) fail("docNumber", "Укажите номер");
      if (!state.docIssuer.trim()) fail("docIssuer", "Укажите орган выдачи");
      if (!state.docIssueDate) fail("docIssueDate", "Укажите дату выдачи");
      if (!state.docExpiry) fail("docExpiry", "Укажите срок действия");
      else if (state.docIssueDate && !validateDateOrder(state.docIssueDate, state.docExpiry))
        fail("docExpiry", "Срок действия не может быть раньше даты выдачи");
      if (!state.docFile) fail("docFile", "Прикрепите скан документа");
    }

    if (step.id === "education") {
      let hasValid = false;
      state.education.forEach((edu, i) => {
        const p = `edu-${i}`;
        if (!edu.level) fail(`${p}-level`, "Укажите уровень");
        if (!edu.institution.trim()) fail(`${p}-institution`, "Укажите учебное заведение");
        if (!edu.year) fail(`${p}-year`, "Укажите год");
        else if (parseInt(edu.year, 10) > new Date().getFullYear()) fail(`${p}-year`, "Год не может быть в будущем");
        if (!edu.specialty.trim()) fail(`${p}-specialty`, "Укажите специальность");
        if (edu.level && edu.institution.trim() && edu.year && edu.specialty.trim()) hasValid = true;
      });
      if (!hasValid) ok = false;
    }

    if (step.id === "training") {
      if (state.trainingMode === "has") {
        if (state.training.length === 0) {
          ok = false;
          panelBody.querySelector(".cards-list")?.insertAdjacentHTML(
            "beforebegin",
            '<div class="form-error" style="margin-bottom:12px">Добавьте курс или выберите «Нет сведений»</div>'
          );
        }
      }
    }

    if (step.id === "employment") {
      if (state.employmentMode === "has") {
        let hasValid = false;
        state.employment.forEach((emp, i) => {
          const p = `emp-${i}`;
          if (!emp.org.trim()) fail(`${p}-org`, "Укажите организацию");
          if (!emp.position.trim()) fail(`${p}-position`, "Укажите должность");
          if (!emp.startDate) fail(`${p}-startDate`, "Укажите дату начала");
          if (!emp.current && emp.endDate && !validateDateOrder(emp.startDate, emp.endDate))
            fail(`${p}-endDate`, "Дата окончания не может быть раньше начала");
          if (emp.org.trim() && emp.position.trim() && emp.startDate) hasValid = true;
        });
        if (!hasValid) ok = false;
      }
    }

    if (step.id === "family") {
      if (!state.emergencyName.trim()) fail("emergencyName", "Укажите ФИО");
      if (!state.emergencyRelation.trim()) fail("emergencyRelation", "Укажите степень родства");
      if (!validatePhone(state.emergencyPhone)) fail("emergencyPhone", "Укажите телефон");
    }

    if (step.id === "military") {
      if (state.militaryMode === "yes" && !state.militaryDuty) fail("militaryDuty", "Укажите отношение к воинской обязанности");
    }

    if (step.id === "review") {
      if (!state.confirmAccuracy) fail("confirmAccuracy", "Подтвердите достоверность");
      if (!state.confirmConsent) fail("confirmConsent", "Дайте согласие на обработку данных");
      const issues = collectIssues();
      if (issues.required.length > 0) ok = false;
    }

    if (firstBad) firstBad.scrollIntoView({ behavior: "smooth", block: "center" });
    return ok;
  }

  function collectIssues() {
    const required = [];
    const docs = [];

    if (!state.lastName.trim()) required.push("Фамилия");
    if (!state.firstName.trim()) required.push("Имя");
    if (!validateIin(state.iin)) required.push("ИИН (12 цифр)");
    if (!state.birthDate) required.push("Дата рождения");
    if (!state.gender) required.push("Пол");
    if (!state.citizenship) required.push("Гражданство");
    if (!state.maritalStatus) required.push("Семейное положение");
    if (!state.photoFile) { required.push("Фото сотрудника"); docs.push("Фото сотрудника"); }
    if (!validatePhone(state.phone)) required.push("Мобильный телефон");
    if (!state.regAddress.trim()) required.push("Адрес регистрации");
    if (!state.liveAddress.trim()) required.push("Адрес проживания");
    if (!state.docType) required.push("Тип документа");
    if (!state.docNumber.trim()) required.push("Номер документа");
    if (!state.docIssuer.trim()) required.push("Кем выдан документ");
    if (!state.docIssueDate) required.push("Дата выдачи документа");
    if (!state.docExpiry) required.push("Срок действия документа");
    if (!state.docFile) docs.push("Скан удостоверения личности");
    const eduOk = state.education.some((e) => e.level && e.institution.trim() && e.year && e.specialty.trim());
    if (!eduOk) required.push("Сведения об образовании");
    if (state.employmentMode === "has") {
      const empOk = state.employment.some((e) => e.org.trim() && e.position.trim() && e.startDate);
      if (!empOk) required.push("Сведения о местах работы");
    }
    if (!state.emergencyName.trim()) required.push("Контакт для экстренной связи — ФИО");
    if (!state.emergencyRelation.trim()) required.push("Контакт для экстренной связи — родство");
    if (!validatePhone(state.emergencyPhone)) required.push("Контакт для экстренной связи — телефон");
    if (state.militaryMode === "yes" && !state.militaryDuty) required.push("Воинский учёт — отношение к обязанности");

    return { required, docs };
  }

  function calcProgress() {
    const checks = [
      !!state.lastName.trim(),
      !!state.firstName.trim(),
      validateIin(state.iin),
      !!state.birthDate,
      !!state.gender,
      !!state.citizenship,
      !!state.maritalStatus,
      !!state.photoFile,
      validatePhone(state.phone),
      !!state.regAddress.trim(),
      !!state.liveAddress.trim(),
      !!state.docType,
      !!state.docNumber.trim(),
      !!state.docIssuer.trim(),
      !!state.docIssueDate,
      !!state.docExpiry,
      !!state.docFile,
      state.education.some((e) => e.level && e.institution.trim() && e.year && e.specialty.trim()),
      state.employmentMode === "none" || state.employment.some((e) => e.org.trim() && e.position.trim() && e.startDate),
      !!state.emergencyName.trim(),
      !!state.emergencyRelation.trim(),
      validatePhone(state.emergencyPhone),
      state.militaryMode !== "yes" || !!state.militaryDuty,
      state.trainingMode !== "has" || state.training.length > 0,
    ];
    const done = checks.filter(Boolean).length;
    return Math.round((done / checks.length) * 100);
  }

  function updateProgressUI() {
    const pct = calcProgress();
    const fill = document.querySelector(".panel__progress-fill");
    const text = document.querySelector(".panel__progress-text");
    if (fill) fill.style.width = `${pct}%`;
    if (text) text.textContent = `Заполнено ${pct}%`;
  }

  function renderSidebar() {
    sidebar.innerHTML = `
      <div class="sidebar__brand">
        <div class="sidebar__logo">CS</div>
        <div>
          <div class="sidebar__title">Анкета нового сотрудника</div>
          <div class="sidebar__subtitle">Оформление на работу</div>
        </div>
      </div>
      <ol class="stepper">
        ${STEPS.map((s, i) => {
          let cls = "stepper__item";
          if (i === currentIndex) cls += " stepper__item--active";
          else if (i < currentIndex) cls += " stepper__item--completed";
          if (i <= currentIndex && i !== currentIndex) cls += " stepper__item--clickable";
          if (i < currentIndex) cls += " stepper__item--clickable";
          const dotContent =
            i < currentIndex ? "✓" : s.id === "welcome" ? "○" : s.id === "success" ? "★" : String(s.stepNum || "");
          return `<li class="${cls}" data-goto="${i}" role="button" tabindex="0">
            <span class="stepper__dot">${dotContent}</span>
            <span class="stepper__label">${esc(s.label)}</span>
          </li>`;
        }).join("")}
      </ol>`;

    sidebar.querySelectorAll(".stepper__item--clickable, .stepper__item--completed").forEach((el) => {
      el.addEventListener("click", () => {
        const idx = parseInt(el.dataset.goto, 10);
        if (idx < currentIndex && idx !== currentIndex) goTo(idx);
      });
    });

    mobileStepper.innerHTML = STEPS.map((s, i) => {
      let cls = "mobile-stepper__pill";
      if (i === currentIndex) cls += " mobile-stepper__pill--active";
      else if (i < currentIndex) cls += " mobile-stepper__pill--done";
      return `<span class="${cls}">${esc(s.label)}</span>`;
    }).join("");
  }

  function renderWelcome() {
    panelHeader.innerHTML = "";
    panelBody.innerHTML = `
      <div class="hero-screen">
        <div class="hero-screen__icon">📋</div>
        <h1>Анкета нового сотрудника</h1>
        <p><strong>Анкета для оформления на работу</strong></p>
        <p>Заполните анкету, чтобы мы могли оформить ваш приём. Примерное время: <strong>20–30 минут</strong>.</p>
        <ul>
          <li>Можно сохранить прогресс и продолжить позже</li>
          <li>После отправки сведения будут направлены в отдел кадров</li>
          <li>Заполняйте данные как в документе, удостоверяющем личность</li>
          <li>Для быстрого показа нажмите «Заполнить демо-данными» в верхней панели</li>
        </ul>
      </div>`;
    panelFooter.innerHTML = `
      <div class="panel__hint"></div>
      <div class="panel__actions">
        <button type="button" class="btn btn--primary btn--large" id="btnStart">Начать заполнение</button>
      </div>`;
    $("#btnStart").addEventListener("click", () => goTo(1));
  }

  function renderBasic() {
    panelBody.innerHTML = `<div class="form-grid">
      ${fieldHtml({ id: "lastName", label: "Фамилия", required: true, value: state.lastName })}
      ${fieldHtml({ id: "firstName", label: "Имя", required: true, value: state.firstName })}
      ${fieldHtml({ id: "middleName", label: "Отчество", value: state.middleName, full: true })}
      ${fieldHtml({ id: "iin", label: "ИИН", required: true, hint: "12 цифр без пробелов", value: state.iin })}
      ${fieldHtml({ id: "birthDate", label: "Дата рождения", required: true, type: "date", value: state.birthDate })}
      ${fieldHtml({
        id: "gender",
        label: "Пол",
        required: true,
        type: "radio",
        value: state.gender,
        full: true,
        options: [
          { value: "male", label: "Мужской" },
          { value: "female", label: "Женский" },
        ],
      })}
      ${fieldHtml({ id: "birthPlace", label: "Место рождения", hint: "Город, область", value: state.birthPlace, full: true })}
      ${fieldHtml({
        id: "citizenship",
        label: "Гражданство",
        required: true,
        type: "select",
        value: state.citizenship,
        options: [
          { value: "", label: "— Выберите —" },
          { value: "Казахстан", label: "Казахстан" },
          { value: "Россия", label: "Россия" },
          { value: "Другое", label: "Другое" },
        ],
      })}
      ${fieldHtml({ id: "nationality", label: "Национальность", value: state.nationality })}
      ${fieldHtml({
        id: "maritalStatus",
        label: "Семейное положение",
        required: true,
        type: "select",
        value: state.maritalStatus,
        options: [
          { value: "", label: "— Выберите —" },
          { value: "single", label: "Холост / Не замужем" },
          { value: "married", label: "Женат / Замужем" },
          { value: "divorced", label: "Разведён(а)" },
          { value: "widowed", label: "Вдовец / Вдова" },
        ],
      })}
      ${fieldHtml({
        id: "photoFile",
        label: "Фото",
        required: true,
        type: "file",
        accept: "image/*",
        hint: "Фото 3×4 или 4×6, JPG или PNG",
        value: state.photoFile?.name,
        full: true,
      })}
    </div>`;
    bindFields(panelBody);
  }

  function renderContact() {
    panelBody.innerHTML = `<div class="form-grid">
      ${fieldHtml({ id: "phone", label: "Мобильный телефон", required: true, type: "tel", hint: "+7 …", value: state.phone })}
      ${fieldHtml({ id: "phoneAlt", label: "Дополнительный телефон", type: "tel", value: state.phoneAlt })}
      ${fieldHtml({ id: "email", label: "Email", type: "email", hint: "Необязательно", value: state.email, full: true })}
      ${fieldHtml({ id: "regAddress", label: "Адрес регистрации", required: true, type: "textarea", value: state.regAddress, full: true })}
      ${fieldHtml({ id: "liveAddress", label: "Адрес проживания", required: true, type: "textarea", value: state.liveAddress, full: true })}
      ${fieldHtml({
        id: "sameAddress",
        label: "Адрес проживания совпадает с адресом регистрации",
        type: "checkbox",
        checked: state.sameAddress,
        full: true,
      })}
    </div>`;
    bindFields(panelBody);
    if (state.sameAddress) {
      const live = $("#liveAddress");
      if (live) live.disabled = true;
    }
  }

  function renderDocument() {
    panelBody.innerHTML = `<div class="form-grid">
      ${fieldHtml({
        id: "docType",
        label: "Тип документа",
        required: true,
        type: "select",
        value: state.docType,
        full: true,
        options: [
          { value: "", label: "— Выберите —" },
          { value: "id_kz", label: "Удостоверение личности РК" },
          { value: "passport_kz", label: "Паспорт РК" },
          { value: "passport_foreign", label: "Паспорт иностранного гражданина" },
          { value: "residence", label: "Вид на жительство" },
        ],
      })}
      ${fieldHtml({ id: "docNumber", label: "Номер документа", required: true, value: state.docNumber })}
      ${fieldHtml({ id: "docIssuer", label: "Кем выдан", required: true, value: state.docIssuer, full: true })}
      ${fieldHtml({ id: "docIssueDate", label: "Дата выдачи", required: true, type: "date", value: state.docIssueDate })}
      ${fieldHtml({ id: "docExpiry", label: "Срок действия", required: true, type: "date", value: state.docExpiry })}
      ${fieldHtml({
        id: "docFile",
        label: "Прикрепить документ",
        required: true,
        type: "file",
        accept: "image/*,.pdf",
        value: state.docFile?.name,
        full: true,
      })}
    </div>`;
    bindFields(panelBody);
  }

  function educationCard(edu, index) {
    const p = `edu-${index}`;
    return `<div class="card" data-card-id="${edu.id}">
      <div class="card__header">
        <h3 class="card__title">Образование ${index + 1}</h3>
        <div class="card__actions">${state.education.length > 1 ? `<button type="button" class="btn-icon" data-remove-edu="${index}">Удалить</button>` : ""}</div>
      </div>
      <div class="card__body form-grid">
        ${fieldHtml({
          id: `${p}-level`,
          label: "Уровень образования",
          required: true,
          type: "select",
          value: edu.level,
          options: [
            { value: "", label: "— Выберите —" },
            { value: "secondary", label: "Среднее" },
            { value: "secondary_spec", label: "Среднее специальное" },
            { value: "higher", label: "Высшее" },
            { value: "postgrad", label: "Послевузовское" },
          ],
        })}
        ${fieldHtml({ id: `${p}-institution`, label: "Учебное заведение", required: true, value: edu.institution })}
        ${fieldHtml({ id: `${p}-country`, label: "Страна", value: edu.country })}
        ${fieldHtml({ id: `${p}-year`, label: "Год окончания", required: true, type: "number", value: edu.year })}
        ${fieldHtml({ id: `${p}-specialty`, label: "Специальность", required: true, value: edu.specialty, full: true })}
        ${fieldHtml({ id: `${p}-qualification`, label: "Квалификация", value: edu.qualification })}
        ${fieldHtml({ id: `${p}-diplomaNum`, label: "Номер диплома", value: edu.diplomaNum })}
        ${fieldHtml({ id: `${p}-diplomaDate`, label: "Дата выдачи диплома", type: "date", value: edu.diplomaDate })}
        ${fieldHtml({
          id: `${p}-diplomaFile`,
          label: "Прикрепить диплом",
          type: "file",
          accept: "image/*,.pdf",
          value: edu.diplomaFile?.name,
          full: true,
        })}
      </div>
    </div>`;
  }

  function bindEducationCards() {
    state.education.forEach((edu, i) => {
      const p = `edu-${i}`;
      const map = {
        [`${p}-level`]: "level",
        [`${p}-institution`]: "institution",
        [`${p}-country`]: "country",
        [`${p}-year`]: "year",
        [`${p}-specialty`]: "specialty",
        [`${p}-qualification`]: "qualification",
        [`${p}-diplomaNum`]: "diplomaNum",
        [`${p}-diplomaDate`]: "diplomaDate",
      };
      Object.entries(map).forEach(([fid, key]) => {
        const el = document.getElementById(fid);
        if (!el) return;
        el.addEventListener("input", () => {
          edu[key] = el.value;
          updateProgressUI();
        });
        el.addEventListener("change", () => {
          if (el.type === "file") edu.diplomaFile = el.files[0] || null;
          else edu[key] = el.value;
          updateProgressUI();
        });
      });
      const fileEl = document.getElementById(`${p}-diplomaFile`);
      if (fileEl) {
        const wrap = fileEl.closest("[data-file-wrap]");
        if (wrap) wrap.addEventListener("click", () => fileEl.click());
      }
    });
    panelBody.querySelectorAll("[data-remove-edu]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.education.splice(parseInt(btn.dataset.removeEdu, 10), 1);
        renderStep(currentIndex);
      });
    });
    $("#btnAddEdu")?.addEventListener("click", () => {
      state.education.push({
        id: nextCardId("edu"),
        level: "",
        institution: "",
        country: "Казахстан",
        year: "",
        specialty: "",
        qualification: "",
        diplomaNum: "",
        diplomaDate: "",
        diplomaFile: null,
      });
      renderStep(currentIndex);
    });
  }

  function renderEducation() {
    panelBody.innerHTML = `
      <p class="form-hint" style="margin-bottom:20px">Добавьте все учебные заведения, начиная с последнего.</p>
      <div class="cards-list">${state.education.map(educationCard).join("")}</div>
      <button type="button" class="btn-add" id="btnAddEdu">+ Добавить образование</button>`;
    bindEducationCards();
  }

  function trainingCard(tr, index) {
    const p = `tr-${index}`;
    return `<div class="card">
      <div class="card__header">
        <h3 class="card__title">Курс ${index + 1}</h3>
        <button type="button" class="btn-icon" data-remove-tr="${index}">Удалить</button>
      </div>
      <div class="card__body form-grid">
        ${fieldHtml({ id: `${p}-name`, label: "Название курса / сертификата", value: tr.name })}
        ${fieldHtml({ id: `${p}-org`, label: "Организация", value: tr.org })}
        ${fieldHtml({ id: `${p}-start`, label: "Дата начала", type: "date", value: tr.start })}
        ${fieldHtml({ id: `${p}-end`, label: "Дата окончания", type: "date", value: tr.end })}
        ${fieldHtml({ id: `${p}-hours`, label: "Количество часов", type: "number", value: tr.hours })}
        ${fieldHtml({ id: `${p}-cert`, label: "Номер сертификата", value: tr.certNum })}
        ${fieldHtml({ id: `${p}-file`, label: "Прикрепить сертификат", type: "file", accept: "image/*,.pdf", value: tr.file?.name, full: true })}
      </div>
    </div>`;
  }

  function bindTraining() {
    panelBody.querySelectorAll(".toggle-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.trainingMode = btn.dataset.mode;
        if (state.trainingMode === "has" && state.training.length === 0) {
          state.training.push({ id: nextCardId("tr"), name: "", org: "", start: "", end: "", hours: "", certNum: "", file: null });
        }
        renderStep(currentIndex);
      });
    });
    state.training.forEach((tr, i) => {
      ["name", "org", "start", "end", "hours", "certNum"].forEach((key) => {
        const el = document.getElementById(`tr-${i}-${key === "certNum" ? "cert" : key}`);
        if (!el) return;
        el.addEventListener("input", () => {
          tr[key] = el.value;
        });
      });
      const f = document.getElementById(`tr-${i}-file`);
      if (f) {
        f.addEventListener("change", () => {
          tr.file = f.files[0] || null;
        });
        f.closest("[data-file-wrap]")?.addEventListener("click", () => f.click());
      }
    });
    panelBody.querySelectorAll("[data-remove-tr]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.training.splice(parseInt(btn.dataset.removeTr, 10), 1);
        renderStep(currentIndex);
      });
    });
    $("#btnAddTr")?.addEventListener("click", () => {
      state.training.push({ id: nextCardId("tr"), name: "", org: "", start: "", end: "", hours: "", certNum: "", file: null });
      renderStep(currentIndex);
    });
  }

  function renderTraining() {
    panelBody.innerHTML = `
      <div class="toggle-row">
        <button type="button" class="toggle-btn${state.trainingMode === "has" ? " toggle-btn--active" : ""}" data-mode="has">Есть сведения</button>
        <button type="button" class="toggle-btn${state.trainingMode === "none" ? " toggle-btn--active" : ""}" data-mode="none">Нет сведений</button>
      </div>
      ${state.trainingMode === "has" ? `<div class="cards-list">${state.training.map(trainingCard).join("")}</div><button type="button" class="btn-add" id="btnAddTr">+ Добавить курс</button>` : "<p class='form-hint'>Раздел отмечен как «нет сведений».</p>"}`;
    bindTraining();
  }

  function employmentCard(emp, index) {
    const p = `emp-${index}`;
    return `<div class="card">
      <div class="card__header">
        <h3 class="card__title">Место работы ${index + 1}</h3>
        ${state.employment.length > 1 ? `<button type="button" class="btn-icon" data-remove-emp="${index}">Удалить</button>` : ""}
      </div>
      <div class="card__body form-grid">
        ${fieldHtml({ id: `${p}-org`, label: "Организация", required: true, value: emp.org })}
        ${fieldHtml({ id: `${p}-position`, label: "Должность", required: true, value: emp.position })}
        ${fieldHtml({ id: `${p}-startDate`, label: "Дата начала", required: true, type: "date", value: emp.startDate })}
        ${fieldHtml({ id: `${p}-endDate`, label: "Дата окончания", type: "date", value: emp.endDate })}
        ${fieldHtml({ id: `${p}-current`, label: "Работаю по настоящее время", type: "checkbox", checked: emp.current, full: true })}
        ${fieldHtml({ id: `${p}-reason`, label: "Причина увольнения", value: emp.reason, full: true })}
        ${fieldHtml({ id: `${p}-location`, label: "Страна / город", value: emp.location })}
        ${fieldHtml({ id: `${p}-file`, label: "Подтверждающий документ", type: "file", accept: "image/*,.pdf", value: emp.docFile?.name, full: true })}
      </div>
    </div>`;
  }

  function bindEmployment() {
    panelBody.querySelectorAll(".toggle-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.employmentMode = btn.dataset.mode;
        renderStep(currentIndex);
      });
    });
    state.employment.forEach((emp, i) => {
      const fields = ["org", "position", "startDate", "endDate", "reason", "location"];
      fields.forEach((key) => {
        const el = document.getElementById(`emp-${i}-${key}`);
        if (!el) return;
        el.addEventListener("input", () => {
          emp[key] = el.value;
          updateProgressUI();
        });
      });
      const cur = document.getElementById(`emp-${i}-current`);
      const end = document.getElementById(`emp-${i}-endDate`);
      if (cur) {
        cur.addEventListener("change", () => {
          emp.current = cur.checked;
          if (end) end.disabled = cur.checked;
          updateProgressUI();
        });
        if (end) end.disabled = emp.current;
      }
      const f = document.getElementById(`emp-${i}-file`);
      if (f) {
        f.addEventListener("change", () => (emp.docFile = f.files[0] || null));
        f.closest("[data-file-wrap]")?.addEventListener("click", () => f.click());
      }
    });
    panelBody.querySelectorAll("[data-remove-emp]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.employment.splice(parseInt(btn.dataset.removeEmp, 10), 1);
        renderStep(currentIndex);
      });
    });
    $("#btnAddEmp")?.addEventListener("click", () => {
      state.employment.push({ id: nextCardId("emp"), org: "", position: "", startDate: "", endDate: "", current: false, reason: "", location: "", docFile: null });
      renderStep(currentIndex);
    });
  }

  function renderEmployment() {
    panelBody.innerHTML = `
      <div class="toggle-row">
        <button type="button" class="toggle-btn${state.employmentMode === "has" ? " toggle-btn--active" : ""}" data-mode="has">Есть опыт работы</button>
        <button type="button" class="toggle-btn${state.employmentMode === "none" ? " toggle-btn--active" : ""}" data-mode="none">Нет опыта работы</button>
      </div>
      ${state.employmentMode === "has" ? `<div class="cards-list">${state.employment.map(employmentCard).join("")}</div><button type="button" class="btn-add" id="btnAddEmp">+ Добавить место работы</button>` : "<p class='form-hint'>Опыт работы не указан.</p>"}`;
    bindEmployment();
  }

  function childCard(ch, index) {
    return `<div class="card">
      <div class="card__header">
        <h3 class="card__title">Ребёнок ${index + 1}</h3>
        <button type="button" class="btn-icon" data-remove-child="${index}">Удалить</button>
      </div>
      <div class="card__body form-grid">
        ${fieldHtml({ id: `child-${index}-name`, label: "ФИО", value: ch.name })}
        ${fieldHtml({ id: `child-${index}-birth`, label: "Дата рождения", type: "date", value: ch.birth })}
      </div>
    </div>`;
  }

  function bindFamily() {
    panelBody.querySelectorAll("[data-spouse-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.spouseMode = btn.dataset.spouseMode;
        renderStep(currentIndex);
      });
    });
    panelBody.querySelectorAll("[data-children-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.childrenMode = btn.dataset.childrenMode;
        if (state.childrenMode === "has" && state.children.length === 0) {
          state.children.push({ name: "", birth: "" });
        }
        renderStep(currentIndex);
      });
    });
    bindFields(panelBody);
    state.children.forEach((ch, i) => {
      const n = document.getElementById(`child-${i}-name`);
      const b = document.getElementById(`child-${i}-birth`);
      if (n) n.addEventListener("input", () => (ch.name = n.value));
      if (b) b.addEventListener("input", () => (ch.birth = b.value));
    });
    panelBody.querySelectorAll("[data-remove-child]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.children.splice(parseInt(btn.dataset.removeChild, 10), 1);
        renderStep(currentIndex);
      });
    });
    $("#btnAddChild")?.addEventListener("click", () => {
      state.children.push({ name: "", birth: "" });
      renderStep(currentIndex);
    });
  }

  function renderFamily() {
    panelBody.innerHTML = `
      <div class="section-block">
        <h3 class="section-block__title">Супруг / супруга</h3>
        <div class="toggle-row">
          <button type="button" class="toggle-btn${state.spouseMode === "na" ? " toggle-btn--active" : ""}" data-spouse-mode="na">Не применимо</button>
          <button type="button" class="toggle-btn${state.spouseMode === "fill" ? " toggle-btn--active" : ""}" data-spouse-mode="fill">Заполнить</button>
        </div>
        ${state.spouseMode === "fill" ? `<div class="form-grid">
          ${fieldHtml({ id: "spouseName", label: "ФИО", value: state.spouseName })}
          ${fieldHtml({ id: "spouseBirth", label: "Дата рождения", type: "date", value: state.spouseBirth })}
          ${fieldHtml({ id: "spouseWork", label: "Место работы", value: state.spouseWork, full: true })}
          ${fieldHtml({ id: "spousePhone", label: "Телефон", type: "tel", value: state.spousePhone })}
        </div>` : ""}
      </div>
      <div class="section-block">
        <h3 class="section-block__title">Дети</h3>
        <div class="toggle-row">
          <button type="button" class="toggle-btn${state.childrenMode === "none" ? " toggle-btn--active" : ""}" data-children-mode="none">Детей нет</button>
          <button type="button" class="toggle-btn${state.childrenMode === "has" ? " toggle-btn--active" : ""}" data-children-mode="has">Добавить сведения</button>
        </div>
        ${state.childrenMode === "has" ? `<div class="cards-list">${state.children.map(childCard).join("")}</div><button type="button" class="btn-add" id="btnAddChild">+ Добавить ребёнка</button>` : ""}
      </div>
      <div class="section-block">
        <h3 class="section-block__title">Контактное лицо для экстренной связи</h3>
        <div class="form-grid">
          ${fieldHtml({ id: "emergencyName", label: "ФИО", required: true, value: state.emergencyName })}
          ${fieldHtml({ id: "emergencyRelation", label: "Степень родства / отношение", required: true, value: state.emergencyRelation })}
          ${fieldHtml({ id: "emergencyPhone", label: "Телефон", required: true, type: "tel", value: state.emergencyPhone, full: true })}
        </div>
      </div>`;
    bindFamily();
  }

  function bindMilitary() {
    panelBody.querySelectorAll("[data-mil-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.militaryMode = btn.dataset.milMode;
        renderStep(currentIndex);
      });
    });
    bindFields(panelBody);
  }

  function renderMilitary() {
    panelBody.innerHTML = `
      <div class="toggle-row">
        <button type="button" class="toggle-btn${state.militaryMode === "yes" ? " toggle-btn--active" : ""}" data-mil-mode="yes">Да, заполнить сведения</button>
        <button type="button" class="toggle-btn${state.militaryMode === "na" ? " toggle-btn--active" : ""}" data-mil-mode="na">Не применимо</button>
      </div>
      ${state.militaryMode === "yes" ? `<div class="form-grid">
        ${fieldHtml({
          id: "militaryDuty",
          label: "Отношение к воинской обязанности",
          required: true,
          type: "select",
          value: state.militaryDuty,
          options: [
            { value: "", label: "— Выберите —" },
            { value: "liable", label: "Военнообязанный" },
            { value: "registered", label: "Состоит на учёте" },
            { value: "exempt", label: "Освобождён" },
          ],
          full: true,
        })}
        ${fieldHtml({ id: "militaryRank", label: "Воинское звание", value: state.militaryRank })}
        ${fieldHtml({ id: "militaryCategory", label: "Категория запаса", value: state.militaryCategory })}
        ${fieldHtml({ id: "militaryProfile", label: "Состав / профиль", value: state.militaryProfile, full: true })}
        ${fieldHtml({
          id: "militaryDocType",
          label: "Документ",
          type: "select",
          value: state.militaryDocType,
          options: [
            { value: "", label: "— Выберите —" },
            { value: "military_id", label: "Военный билет" },
            { value: "registration", label: "Приписное свидетельство" },
          ],
        })}
        ${fieldHtml({ id: "militaryDocNum", label: "Номер документа", value: state.militaryDocNum })}
        ${fieldHtml({ id: "militaryDocDate", label: "Дата выдачи", type: "date", value: state.militaryDocDate })}
        ${fieldHtml({ id: "militaryDocFile", label: "Прикрепить документ", type: "file", accept: "image/*,.pdf", value: state.militaryDocFile?.name, full: true })}
      </div>` : "<p class='form-hint'>Раздел отмечен как «не применимо».</p>"}`;
    bindMilitary();
  }

  function langCard(lg, index) {
    return `<div class="card">
      <div class="card__header">
        <h3 class="card__title">Язык ${index + 1}</h3>
        <button type="button" class="btn-icon" data-remove-lang="${index}">Удалить</button>
      </div>
      <div class="card__body form-grid">
        ${fieldHtml({ id: `lang-${index}-name`, label: "Язык", value: lg.name })}
        ${fieldHtml({
          id: `lang-${index}-level`,
          label: "Уровень владения",
          type: "select",
          value: lg.level,
          options: [
            { value: "", label: "— Выберите —" },
            { value: "basic", label: "Базовый" },
            { value: "medium", label: "Средний" },
            { value: "advanced", label: "Свободный" },
          ],
        })}
      </div>
    </div>`;
  }

  function bindAdditional() {
    panelBody.querySelectorAll("[data-add-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.additionalMode = btn.dataset.addMode;
        renderStep(currentIndex);
      });
    });
    bindFields(panelBody);
    panelBody.querySelectorAll("[data-has-license]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.hasLicense = btn.dataset.hasLicense;
        renderStep(currentIndex);
      });
    });
    state.languages.forEach((lg, i) => {
      const n = document.getElementById(`lang-${i}-name`);
      const l = document.getElementById(`lang-${i}-level`);
      if (n) n.addEventListener("input", () => (lg.name = n.value));
      if (l) l.addEventListener("change", () => (lg.level = l.value));
    });
    panelBody.querySelectorAll("[data-remove-lang]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.languages.splice(parseInt(btn.dataset.removeLang, 10), 1);
        renderStep(currentIndex);
      });
    });
    $("#btnAddLang")?.addEventListener("click", () => {
      state.languages.push({ name: "", level: "" });
      state.additionalMode = "has";
      renderStep(currentIndex);
    });
    $("#btnAddAward")?.addEventListener("click", () => {
      state.awards.push({ title: "", year: "" });
      state.additionalMode = "has";
      renderStep(currentIndex);
    });
    state.awards.forEach((aw, i) => {
      const t = document.getElementById(`award-${i}-title`);
      const y = document.getElementById(`award-${i}-year`);
      if (t) t.addEventListener("input", () => (aw.title = t.value));
      if (y) y.addEventListener("input", () => (aw.year = y.value));
    });
    panelBody.querySelectorAll("[data-remove-award]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.awards.splice(parseInt(btn.dataset.removeAward, 10), 1);
        renderStep(currentIndex);
      });
    });
  }

  function renderAdditional() {
    panelBody.innerHTML = `
      <div class="toggle-row">
        <button type="button" class="toggle-btn${state.additionalMode === "has" ? " toggle-btn--active" : ""}" data-add-mode="has">Есть сведения</button>
        <button type="button" class="toggle-btn${state.additionalMode === "none" ? " toggle-btn--active" : ""}" data-add-mode="none">Нет сведений для этого раздела</button>
      </div>
      ${state.additionalMode === "has" ? `
        <div class="section-block">
          <h3 class="section-block__title">Владение языками</h3>
          <div class="cards-list">${state.languages.map(langCard).join("")}</div>
          <button type="button" class="btn-add" id="btnAddLang">+ Добавить язык</button>
        </div>
        <div class="section-block">
          <h3 class="section-block__title">Водительское удостоверение</h3>
          <div class="toggle-row">
            <button type="button" class="toggle-btn${state.hasLicense === "yes" ? " toggle-btn--active" : ""}" data-has-license="yes">Есть</button>
            <button type="button" class="toggle-btn${state.hasLicense === "no" ? " toggle-btn--active" : ""}" data-has-license="no">Нет</button>
          </div>
          ${state.hasLicense === "yes" ? `<div class="form-grid">
            ${fieldHtml({ id: "licenseCategories", label: "Категории", value: state.licenseCategories, hint: "Например: B" })}
            ${fieldHtml({ id: "licenseExpiry", label: "Срок действия", type: "date", value: state.licenseExpiry })}
          </div>` : ""}
        </div>
        <div class="section-block">
          <h3 class="section-block__title">Учёная степень</h3>
          <div class="form-grid">
            ${fieldHtml({ id: "academicDegree", label: "Учёная степень", value: state.academicDegree })}
            ${fieldHtml({ id: "academicTitle", label: "Учёное звание", value: state.academicTitle })}
          </div>
        </div>
        <div class="section-block">
          <h3 class="section-block__title">Награды</h3>
          <div class="cards-list">${state.awards
            .map(
              (aw, i) => `<div class="card"><div class="card__header"><h3 class="card__title">Награда ${i + 1}</h3>
              <button type="button" class="btn-icon" data-remove-award="${i}">Удалить</button></div>
              <div class="card__body form-grid">
              ${fieldHtml({ id: `award-${i}-title`, label: "Награда", value: aw.title })}
              ${fieldHtml({ id: `award-${i}-year`, label: "Год", type: "number", value: aw.year })}
              </div></div>`
            )
            .join("")}</div>
          <button type="button" class="btn-add" id="btnAddAward">+ Добавить награду</button>
        </div>
        <div class="section-block">
          ${fieldHtml({ id: "otherInfo", label: "Иные сведения", type: "textarea", value: state.otherInfo, hint: "То, что считаете важным сообщить отделу кадров", full: true })}
        </div>` : "<p class='form-hint'>Дополнительные сведения не указаны.</p>"}`;
    bindAdditional();
  }

  function sectionStatus(stepId) {
    const issues = collectIssues();
    const sectionFields = {
      basic: ["Фамилия", "Имя", "ИИН", "Дата рождения", "Пол", "Гражданство", "Семейное положение", "Фото сотрудника"],
      contact: ["Мобильный телефон", "Адрес регистрации", "Адрес проживания"],
      document: ["Тип документа", "Номер документа", "Кем выдан документ", "Дата выдачи документа", "Срок действия документа", "Скан удостоверения личности"],
      education: ["Сведения об образовании"],
      employment: ["Сведения о местах работы"],
      family: ["Контакт для экстренной связи — ФИО", "Контакт для экстренной связи — родство", "Контакт для экстренной связи — телефон"],
      military: ["Воинский учёт — отношение к обязанности"],
    };
    const labels = sectionFields[stepId];
    if (!labels) return { status: "ok", label: "Заполнено" };
    const missing = issues.required.filter((r) => labels.includes(r));
    if (stepId === "employment" && state.employmentMode === "none") return { status: "ok", label: "Не требуется" };
    if (stepId === "training" && state.trainingMode === "none") return { status: "ok", label: "Не требуется" };
    if (stepId === "military" && state.militaryMode === "na") return { status: "ok", label: "Не применимо" };
    if (stepId === "additional" && state.additionalMode === "none") return { status: "ok", label: "Не требуется" };
    if (missing.length > 0) return { status: "err", label: "Не заполнено" };
    if (issues.docs.length && (stepId === "document" || stepId === "basic")) return { status: "warn", label: "Проверьте документы" };
    return { status: "ok", label: "Заполнено" };
  }

  function renderReview() {
    const pct = calcProgress();
    const issues = collectIssues();
    const formSteps = STEPS.filter((s) => s.stepNum);

    panelBody.innerHTML = `
      <div class="review-summary">
        <div class="review-percent">
          <div class="review-percent__value">${pct}%</div>
          <div class="review-percent__label">заполнено</div>
        </div>
        <div>
          <h3 style="margin:0 0 12px;font-size:16px">Разделы анкеты</h3>
          <div class="review-sections">
            ${formSteps
              .filter((s) => s.id !== "review")
              .map((s) => {
                const st = sectionStatus(s.id);
                return `<div class="review-section-item" data-goto-step="${STEPS.indexOf(s)}">
                  <span class="review-section-item__name">${esc(s.title)}</span>
                  <span class="review-status review-status--${st.status === "ok" ? "ok" : st.status === "warn" ? "warn" : "err"}">${esc(st.label)}</span>
                </div>`;
              })
              .join("")}
          </div>
        </div>
        <div class="review-issues${issues.required.length === 0 && issues.docs.length === 0 ? " review-issues--empty" : ""}">
          <h3>${issues.required.length === 0 ? "✓ Обязательные поля заполнены" : "Незаполненные обязательные поля"}</h3>
          <ul>${issues.required.map((i) => `<li>${esc(i)}</li>`).join("") || "<li>Все обязательные поля заполнены</li>"}</ul>
        </div>
        ${issues.docs.length ? `<div class="review-issues"><h3>Отсутствующие документы</h3><ul>${issues.docs.map((d) => `<li>${esc(d)}</li>`).join("")}</ul></div>` : ""}
        <div class="form-grid form-grid--1">
          ${fieldHtml({ id: "confirmAccuracy", label: "Подтверждаю, что сведения указаны верно", type: "checkbox", required: true, checked: state.confirmAccuracy, full: true })}
          ${fieldHtml({ id: "confirmConsent", label: "Даю согласие на обработку персональных данных", type: "checkbox", required: true, checked: state.confirmConsent, full: true })}
        </div>
      </div>`;

    bindFields(panelBody);
    panelBody.querySelectorAll("[data-goto-step]").forEach((el) => {
      el.addEventListener("click", () => goTo(parseInt(el.dataset.gotoStep, 10)));
    });
  }

  function downloadFeedbackForm() {
    const date = new Date().toLocaleDateString("ru-RU");
    const ref = submissionRef || "—";
    const content = [
      "Лист предложений — анкета нового сотрудника (демонстрация)",
      "",
      `Дата: ${date}`,
      `Номер заявки (демо): ${ref}`,
      "",
      "1. Что понравилось?",
      "",
      "",
      "",
      "2. Что неудобно?",
      "",
      "",
      "",
      "3. Какие поля отсутствуют?",
      "",
      "",
      "",
      "4. Какие документы нужно добавить?",
      "",
      "",
      "",
      "5. Общие предложения",
      "",
      "",
      "",
    ].join("\r\n");

    const blob = new Blob(["\uFEFF" + content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "list-predlozhenij-anketa.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  function renderSuccess() {
    if (!submissionRef) {
      const now = new Date();
      const y = now.getFullYear();
      const seq = String(Math.floor(Math.random() * 9000) + 1000);
      submissionRef = `АНК-${y}-${seq}`;
    }
    const submittedAt = new Date().toLocaleString("ru-RU", {
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

    panelHeader.innerHTML = "";
    panelBody.innerHTML = `
      <div class="hero-screen">
        <div class="hero-screen__icon hero-screen__icon--success">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 6L9 17l-5-5"/>
          </svg>
        </div>
        <h1>Анкета отправлена в отдел кадров</h1>
        <p>Спасибо, ${esc(state.firstName || "коллега")}! Ваши сведения успешно переданы в отдел кадров.</p>
        <div class="success-ref">Номер заявки: <strong>${esc(submissionRef)}</strong><br/>Отправлено: ${esc(submittedAt)}</div>
        <p>Отдел кадров проверит анкету. Если потребуется уточнение, с вами свяжутся по указанному телефону${state.email ? " или email" : ""}.</p>
        <div class="hero-screen__next-steps">
          <h2>Что дальше</h2>
          <ol>
            <li>Отдел кадров проверит заполненные сведения</li>
            <li>При необходимости с вами свяжутся для уточнения</li>
            <li>После проверки вас пригласят для оформления документов</li>
          </ol>
        </div>
      </div>`;
    panelFooter.innerHTML = `
      <div class="panel__hint">Это демонстрационный экран. В рабочей версии здесь будет подтверждение отправки.</div>
      <div class="panel__actions">
        <button type="button" class="btn btn--secondary" id="btnDownloadFeedback">Скачать лист предложений</button>
        <button type="button" class="btn btn--secondary" id="btnClose">Закрыть</button>
      </div>`;
    $("#btnDownloadFeedback")?.addEventListener("click", downloadFeedbackForm);
    $("#btnClose")?.addEventListener("click", () => {
      window.close();
    });
  }

  function renderHeader(step) {
    if (step.id === "welcome" || step.id === "success") {
      panelHeader.innerHTML = "";
      return;
    }
    const pct = calcProgress();
    const stepLabel = step.stepNum ? `Шаг ${step.stepNum} из ${TOTAL_FORM_STEPS}` : "";
    panelHeader.innerHTML = `
      <div class="panel__step-meta">
        <span class="panel__step-badge">${stepLabel}</span>
        <span class="panel__progress-text">Заполнено ${pct}%</span>
      </div>
      <div class="panel__progress-bar"><div class="panel__progress-fill" style="width:${pct}%"></div></div>
      <h1 class="panel__title">${esc(step.title)}</h1>
      <p class="panel__desc">${getStepDescription(step.id)}</p>`;
  }

  function getStepDescription(id) {
    const d = {
      basic: "Укажите данные как в документе, удостоверяющем личность.",
      contact: "Как с вами связаться и где вы проживаете.",
      document: "Реквизиты основного документа, удостоверяющего личность.",
      education: "Все учебные заведения, начиная с последнего.",
      training: "Курсы повышения квалификации, если проходили.",
      employment: "Предыдущие места работы или отметьте «нет опыта».",
      family: "Сведения о семье и контакт для экстренной связи.",
      military: "Сведения о воинском учёте, если применимо.",
      additional: "Языки, права, учёная степень и другие сведения.",
      review: "Проверьте анкету перед отправкой в отдел кадров.",
    };
    return d[id] || "";
  }

  function renderFooter(step) {
    if (step.id === "welcome" || step.id === "success") return;

    const isFirst = step.stepNum === 1;
    const isReview = step.id === "review";
    const issues = collectIssues();
    const canSubmit = issues.required.length === 0;

    panelFooter.innerHTML = `
      <div class="panel__hint">Данные сохраняются автоматически. Вы можете продолжить позже.</div>
      <div class="panel__actions">
        ${isFirst ? "" : `<button type="button" class="btn btn--secondary" id="btnBack">Назад</button>`}
        ${isReview
          ? `<button type="button" class="btn btn--success" id="btnSubmit"${canSubmit ? "" : " disabled"} title="${canSubmit ? "" : "Заполните обязательные поля"}">Отправить в отдел кадров</button>`
          : `<button type="button" class="btn btn--primary" id="btnNext">Далее</button>`}
      </div>`;

    $("#btnBack")?.addEventListener("click", () => goTo(currentIndex - 1));
    $("#btnNext")?.addEventListener("click", () => {
      if (validateStep(currentIndex)) goTo(currentIndex + 1);
    });
    $("#btnSubmit")?.addEventListener("click", () => {
      if (validateStep(currentIndex)) goTo(currentIndex + 1);
    });
  }

  function renderStep(index) {
    currentIndex = index;
    const step = STEPS[index];
    renderSidebar();

    switch (step.id) {
      case "welcome":
        renderWelcome();
        return;
      case "basic":
        renderHeader(step);
        renderBasic();
        break;
      case "contact":
        renderHeader(step);
        renderContact();
        break;
      case "document":
        renderHeader(step);
        renderDocument();
        break;
      case "education":
        renderHeader(step);
        renderEducation();
        break;
      case "training":
        renderHeader(step);
        renderTraining();
        break;
      case "employment":
        renderHeader(step);
        renderEmployment();
        break;
      case "family":
        renderHeader(step);
        renderFamily();
        break;
      case "military":
        renderHeader(step);
        renderMilitary();
        break;
      case "additional":
        renderHeader(step);
        renderAdditional();
        break;
      case "review":
        renderHeader(step);
        renderReview();
        break;
      case "success":
        renderSuccess();
        return;
      default:
        break;
    }

    renderFooter(step);
    updateProgressUI();
  }

  function readHashStep() {
    const m = window.location.hash.match(/^#step=(\d+)$/);
    if (!m) return null;
    const n = parseInt(m[1], 10);
    return n >= 0 && n < STEPS.length ? n : null;
  }

  function goTo(index) {
    if (index < 0 || index >= STEPS.length) return;
    if (STEPS[index].id === "success" && STEPS[currentIndex]?.id === "review") {
      submissionRef = "";
    }
    renderStep(index);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /** Demo helper: pifGoToStep(4) in browser console to jump to a step */
  window.pifGoToStep = goTo;

  function boot() {
    const hashStep = readHashStep();
    renderStep(hashStep != null ? hashStep : 0);
  }

  window.addEventListener("hashchange", boot);
  boot();
  $("#btnDemoAutofill")?.addEventListener("click", fillDemoData);
})();
