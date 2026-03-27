export type ResumeLinkField = {
  label: string;
  value: string;
  href?: string;
};

export type ResumeLanguage = {
  name: string;
  level: string;
};

export type ResumeEducation = {
  course: string;
  conclusion: string;
  institution: string;
};

export type ResumeExperience = {
  role: string;
  duration: string;
  company: string;
  summary: string;
};

export type ResumeSolvedProblem = {
  title: string;
  context: string;
  impact: string;
};

export type ResumeSkillGroup = {
  title: string;
  items: string[];
};

export const RESUME_PHOTO_FRAME_STYLE_OPTIONS = [
  {
    value: "editorial",
    label: "Editorial Clean",
    description: "Moldura com bloco deslocado e presença discreta.",
  },
  {
    value: "technical",
    label: "Technical Minimal",
    description: "Geometria mais rígida, borda seca e leitura mais tech.",
  },
] as const;

export type ResumePhotoFrameStyle = (typeof RESUME_PHOTO_FRAME_STYLE_OPTIONS)[number]["value"];

export type ResumeTheme = {
  accentColor: string;
  sidebarBackground: string;
  pageBackground: string;
  fontScale: number;
  sidebarWidth: number;
  photoFrameStyle: ResumePhotoFrameStyle;
  uppercaseSkills: boolean;
};

export type ResumeProfile = {
  fullName: string;
  address: string;
  phone: string;
  email: string;
  linkedin: string;
  github: string;
  portfolio: string;
  maritalStatus: string;
  nationality: string;
  photoDataUrl?: string;
};

export type ResumeDocument = {
  theme: ResumeTheme;
  profile: ResumeProfile;
  languages: ResumeLanguage[];
  education: ResumeEducation[];
  experiences: ResumeExperience[];
  solvedProblems: ResumeSolvedProblem[];
  certifications: string[];
  skillGroups: ResumeSkillGroup[];
};

export type ResumeLocale = "pt" | "en";

export type ResumePreviewCopy = {
  contact: string;
  address: string;
  phone: string;
  email: string;
  linkedin: string;
  github: string;
  portfolio: string;
  maritalStatus: string;
  nationality: string;
  languages: string;
  education: string;
  experience: string;
  certifications: string;
  skills: string;
  solvedProblems: string;
  conclusion: string;
  impact: string;
  print: string;
};

export const DEFAULT_RESUME_LOCALE: ResumeLocale = "pt";
export const RESUME_STORAGE_KEY = "kids-jobs:resume-draft:v1";
export const RESUME_LOCALE_OPTIONS = [
  { value: "pt", label: "Português", shortLabel: "PT" },
  { value: "en", label: "English", shortLabel: "EN" },
] as const;

const RESUME_PREVIEW_COPY: Record<ResumeLocale, ResumePreviewCopy> = {
  pt: {
    contact: "Contato",
    address: "Endereço",
    phone: "Telefone",
    email: "Email",
    linkedin: "LinkedIn",
    github: "GitHub",
    portfolio: "Portfólio",
    maritalStatus: "Estado Civil",
    nationality: "Nacionalidade",
    languages: "Idiomas",
    education: "Formação Acadêmica",
    experience: "Experiência Profissional",
    certifications: "Certificações",
    skills: "Habilidades",
    solvedProblems: "Problemas Resolvidos",
    conclusion: "Conclusão",
    impact: "Impacto",
    print: "Imprimir / Salvar PDF",
  },
  en: {
    contact: "Contact",
    address: "Address",
    phone: "Phone",
    email: "Email",
    linkedin: "LinkedIn",
    github: "GitHub",
    portfolio: "Portfolio",
    maritalStatus: "Marital Status",
    nationality: "Nationality",
    languages: "Languages",
    education: "Education",
    experience: "Professional Experience",
    certifications: "Certifications",
    skills: "Skills",
    solvedProblems: "Solved Problems",
    conclusion: "Graduated",
    impact: "Impact",
    print: "Print / Save PDF",
  },
};

const BASE_RESUME_THEME: ResumeTheme = {
  accentColor: "#4f46e5",
  sidebarBackground: "#f2f4ef",
  pageBackground: "#ffffff",
  fontScale: 1,
  sidebarWidth: 275,
  photoFrameStyle: "editorial",
  uppercaseSkills: false,
};

const BASE_RESUME_PROFILE = {
  fullName: "Samuel Costa Carvalho",
  phone: "(61) 99992-3261",
  email: "sancozta@gmail.com",
  linkedin: "linkedin.com/in/sancozta",
  github: "github.com/sancozta",
  portfolio: "sancozta.com.br",
};

const DEFAULT_RESUME_DATA_PT: ResumeDocument = {
  theme: BASE_RESUME_THEME,
  profile: {
    ...BASE_RESUME_PROFILE,
    address: "QI 5 - Taguatinga Norte - Brasília - DF",
    maritalStatus: "Solteiro",
    nationality: "Brasileiro",
  },
  languages: [
    { name: "Inglês", level: "Intermediário" },
    { name: "Português", level: "Nativo" },
    { name: "Espanhol", level: "Básico" },
  ],
  education: [
    { course: "Ensino Médio", conclusion: "2014", institution: "Escola Estadual de Montalvânia" },
    { course: "Técnico em Administração", conclusion: "2014", institution: "PRONATEC" },
    { course: "Ciência da Computação", conclusion: "2018", institution: "UNICEUB" },
  ],
  experiences: [
    {
      role: "Programador Sênior",
      duration: "4 anos",
      company: "PicPay",
      summary:
        "Desenvolvimento de sistemas com Java, Kotlin e Python, banco de dados MySQL e integração com Jenkins, ArgoCD, SonarQube, Datadog, Dynatrace, Grafana, OpenTelemetry, AWS, JIRA e GitHub. Atuação em casos de uso para transmissão e recepção de dados em open finance e sua extensão para o ecossistema PicPay.",
    },
    {
      role: "Programador Sênior",
      duration: "5 meses",
      company: "CWI Software - Banco BV",
      summary:
        "Criação de sistemas com Java e Python, banco de dados MySQL e Sybase, integrações com Jenkins, SonarQube, JIRA e Bitbucket. Desenvolvimento de motor para concessão de crédito automático para clientes.",
    },
    {
      role: "Programador Pleno",
      duration: "1 ano e 6 meses",
      company: "Globalweb - Superior Tribunal de Justiça",
      summary:
        "Desenvolvimento de sistemas corporativos com Java Spring Boot, DB2 e interface Angular com PrimeNG e Angular Material para plataforma de grande porte.",
    },
    {
      role: "Programador Pleno",
      duration: "1 ano",
      company: "Icomunicação - Faros",
      summary:
        "Desenvolvimento de sistemas com Zend Framework 3 e Angular Material. Entrega de portais com Laravel e WordPress, cursos para CAIXA e websites com Strapi e Gatsby.",
    },
    {
      role: "Analista de Sistemas",
      duration: "1 ano e 6 meses",
      company: "Stefanini IT Solutions",
      summary:
        "Implantações, migrações e treinamentos com sistemas ITSM. Desenvolvimento de APIs em PHP, Node, Java e Python, configuração de servidores Linux e apps mobile com Ionic.",
    },
    {
      role: "Estagiário",
      duration: "2 anos",
      company: "Banco de Brasília - BRB",
      summary:
        "Criação de sistemas para governança interna do BRB com PHP, Kerberos, Oracle, Bootstrap e jQuery.",
    },
    {
      role: "Trabalhos Avulsos",
      duration: "Empresa pessoal",
      company: "Projetos independentes",
      summary:
        "Desenvolvimento e publicação de apps mobile com Flutter, sistemas para escritórios de advocacia, websites, materiais interativos educacionais e home pages de vendas.",
    },
  ],
  solvedProblems: [
    {
      title: "Motor de crédito automático no Banco BV",
      context:
        "Atuei na criação de um motor para concessão automática de crédito, integrando regras de negócio, dados legados e esteiras técnicas do banco.",
      impact:
        "A solução acelerou a decisão de crédito, reduziu esforço operacional e ampliou a capacidade de processamento do fluxo.",
    },
    {
      title: "Casos de uso de Open Finance no ecossistema PicPay",
      context:
        "Participei da evolução dos fluxos de transmissão e recepção de dados em open finance, conectando integrações críticas e requisitos regulatórios.",
      impact:
        "Contribuí para ganho de confiabilidade, observabilidade e escala em integrações estratégicas para o produto.",
    },
  ],
  certifications: [
    "Certificação Spring Boot - Java - Kotlin (ALURA)",
    "Inglês Técnico (COOPLEM IDIOMAS)",
    "Scrum Foundation Professional Certificate - SFPC (CERTIPROF)",
    "Mediador do Programa Intel Aprender (INTEL)",
    "Certificação SQL (SOFTBLUE)",
    "Certificação PHP Orientado a Objetos (B7WEB)",
    "Certificação Docker (ALURA)",
    "Certificação Javascript Avançado III (ALURA)",
    "Certificação Node JS - Inovando no Backend (ALURA)",
    "Certificação Shell Scripting II (ALURA)",
    "Certificação COBIT 5 para Riscos (ISACA)",
    "Certificação React (ALURA)",
    "Certificação Performance Web (ALURA)",
    "Devops Essentials Professional Certificate - DEPC (CERTIPROF)",
    "Apps Android e iOS com Flutter (UDEMY)",
    "Espanhol (Instituto Cervantes)",
    "Certificação Kotlin - Docker - AWS (UDEMY)",
    "Certificação Segurança da Informação (ROADSEC)",
    "Certificação de UI e UX (UDEMY)",
    "Terraform - AWS - Do Básico ao Avançado (ALURA)",
  ],
  skillGroups: [
    {
      title: "Banco de Dados",
      items: ["SQL", "SQLite", "MySQL", "Oracle", "Postgres", "MongoDB", "DB2", "Redis", "DynamoDB", "Aurora"],
    },
    {
      title: "Infraestrutura",
      items: ["Kubernetes", "Docker", "Jenkins", "SonarQube", "Linux", "Nginx", "Datadog", "AWS", "Argo CD", "GitHub Actions"],
    },
    {
      title: "Mundo Java",
      items: ["Java", "Spring Boot", "Kotlin", "Ktor", "Maven", "Gradle", "Hibernate", "GraphQL", "JUnit"],
    },
    {
      title: "Mundo Python",
      items: ["Python", "Django", "Flask", "FastAPI", "Streamlit"],
    },
    {
      title: "Mundo PHP",
      items: ["PHP", "Laravel", "CodeIgniter", "Slim", "Zend Framework", "WordPress"],
    },
    {
      title: "Mundo JavaScript",
      items: ["JavaScript", "Node", "NestJS", "Express", "Electron", "Strapi", "jQuery"],
    },
    {
      title: "Front-end",
      items: ["HTML", "CSS", "Bootstrap", "Angular", "React", "Vue", "PrimeNG", "Angular Material", "Figma", "UI", "UX"],
    },
    {
      title: "Mensageria",
      items: ["Kafka", "RabbitMQ", "SQS", "SNS", "Apache Camel"],
    },
    {
      title: "Mobile",
      items: ["Flutter", "Dart", "Ionic", "React Native", "Firebase"],
    },
    {
      title: "Metodologias e Processos",
      items: ["ITIL", "COBIT 5", "PMP", "SCRUM", "RUP", "UML"],
    },
  ],
};

const DEFAULT_RESUME_DATA_EN: ResumeDocument = {
  theme: BASE_RESUME_THEME,
  profile: {
    ...BASE_RESUME_PROFILE,
    address: "QI 5 - Taguatinga Norte - Brasilia - DF, Brazil",
    maritalStatus: "Single",
    nationality: "Brazilian",
  },
  languages: [
    { name: "English", level: "Intermediate" },
    { name: "Portuguese", level: "Native" },
    { name: "Spanish", level: "Basic" },
  ],
  education: [
    { course: "High School", conclusion: "2014", institution: "Montalvania State School" },
    { course: "Technical Degree in Business Administration", conclusion: "2014", institution: "PRONATEC" },
    { course: "Computer Science", conclusion: "2018", institution: "UNICEUB" },
  ],
  experiences: [
    {
      role: "Senior Software Engineer",
      duration: "4 years",
      company: "PicPay",
      summary:
        "Built systems with Java, Kotlin and Python, using MySQL and integrations with Jenkins, ArgoCD, SonarQube, Datadog, Dynatrace, Grafana, OpenTelemetry, AWS, JIRA and GitHub. Worked on use cases for open finance data transmission and reception, extending them into the PicPay ecosystem.",
    },
    {
      role: "Senior Software Engineer",
      duration: "5 months",
      company: "CWI Software - Banco BV",
      summary:
        "Built systems with Java and Python, using MySQL and Sybase, with integrations to Jenkins, SonarQube, JIRA and Bitbucket. Developed an engine for automatic credit approval.",
    },
    {
      role: "Mid-level Software Engineer",
      duration: "1 year and 6 months",
      company: "Globalweb - Superior Tribunal de Justiça",
      summary:
        "Developed enterprise systems with Java Spring Boot, DB2 and Angular interfaces using PrimeNG and Angular Material for a large-scale platform.",
    },
    {
      role: "Mid-level Software Engineer",
      duration: "1 year",
      company: "Icomunicação - Faros",
      summary:
        "Built systems with Zend Framework 3 and Angular Material. Delivered portals with Laravel and WordPress, courses for CAIXA, and websites using Strapi and Gatsby.",
    },
    {
      role: "Systems Analyst",
      duration: "1 year and 6 months",
      company: "Stefanini IT Solutions",
      summary:
        "Handled implementations, migrations and training for ITSM systems. Developed APIs with PHP, Node, Java and Python, configured Linux servers and delivered mobile apps with Ionic.",
    },
    {
      role: "Intern",
      duration: "2 years",
      company: "Banco de Brasília - BRB",
      summary:
        "Built internal governance systems for BRB using PHP, Kerberos, Oracle, Bootstrap and jQuery.",
    },
    {
      role: "Freelance Projects",
      duration: "Personal business",
      company: "Independent projects",
      summary:
        "Developed and published mobile apps with Flutter, legal office systems, websites, educational interactive materials and sales landing pages.",
    },
  ],
  solvedProblems: [
    {
      title: "Automatic credit engine at Banco BV",
      context:
        "I worked on building an engine for automatic credit approval, integrating business rules, legacy data and the bank's technical delivery pipelines.",
      impact:
        "The solution accelerated credit decisions, reduced operational effort and increased the processing capacity of the flow.",
    },
    {
      title: "Open Finance use cases in the PicPay ecosystem",
      context:
        "I helped evolve data transmission and reception flows in open finance, connecting critical integrations and regulatory requirements.",
      impact:
        "I contributed to higher reliability, observability and scale in strategic product integrations.",
    },
  ],
  certifications: [
    "Spring Boot Certification - Java - Kotlin (ALURA)",
    "Technical English (COOPLEM IDIOMAS)",
    "Scrum Foundation Professional Certificate - SFPC (CERTIPROF)",
    "Intel Teach Program Facilitator (INTEL)",
    "SQL Certification (SOFTBLUE)",
    "Object-Oriented PHP Certification (B7WEB)",
    "Docker Certification (ALURA)",
    "Advanced JavaScript III Certification (ALURA)",
    "Node JS - Backend Innovation Certification (ALURA)",
    "Shell Scripting II Certification (ALURA)",
    "COBIT 5 for Risks Certification (ISACA)",
    "React Certification (ALURA)",
    "Web Performance Certification (ALURA)",
    "DevOps Essentials Professional Certificate - DEPC (CERTIPROF)",
    "Android and iOS Apps with Flutter (UDEMY)",
    "Spanish (Instituto Cervantes)",
    "Kotlin - Docker - AWS Certification (UDEMY)",
    "Information Security Certification (ROADSEC)",
    "UI and UX Certification (UDEMY)",
    "Terraform - AWS - From Basic to Advanced (ALURA)",
  ],
  skillGroups: [
    {
      title: "Databases",
      items: ["SQL", "SQLite", "MySQL", "Oracle", "Postgres", "MongoDB", "DB2", "Redis", "DynamoDB", "Aurora"],
    },
    {
      title: "Infrastructure",
      items: ["Kubernetes", "Docker", "Jenkins", "SonarQube", "Linux", "Nginx", "Datadog", "AWS", "Argo CD", "GitHub Actions"],
    },
    {
      title: "Java Stack",
      items: ["Java", "Spring Boot", "Kotlin", "Ktor", "Maven", "Gradle", "Hibernate", "GraphQL", "JUnit"],
    },
    {
      title: "Python Stack",
      items: ["Python", "Django", "Flask", "FastAPI", "Streamlit"],
    },
    {
      title: "PHP Stack",
      items: ["PHP", "Laravel", "CodeIgniter", "Slim", "Zend Framework", "WordPress"],
    },
    {
      title: "JavaScript Stack",
      items: ["JavaScript", "Node", "NestJS", "Express", "Electron", "Strapi", "jQuery"],
    },
    {
      title: "Front-end",
      items: ["HTML", "CSS", "Bootstrap", "Angular", "React", "Vue", "PrimeNG", "Angular Material", "Figma", "UI", "UX"],
    },
    {
      title: "Messaging",
      items: ["Kafka", "RabbitMQ", "SQS", "SNS", "Apache Camel"],
    },
    {
      title: "Mobile",
      items: ["Flutter", "Dart", "Ionic", "React Native", "Firebase"],
    },
    {
      title: "Methodologies and Processes",
      items: ["ITIL", "COBIT 5", "PMP", "SCRUM", "RUP", "UML"],
    },
  ],
};

const DEFAULT_RESUME_DATA_BY_LOCALE: Record<ResumeLocale, ResumeDocument> = {
  pt: DEFAULT_RESUME_DATA_PT,
  en: DEFAULT_RESUME_DATA_EN,
};

export const DEFAULT_RESUME_DATA: ResumeDocument = DEFAULT_RESUME_DATA_PT;

function cloneResumeData(data: ResumeDocument): ResumeDocument {
  return {
    theme: { ...data.theme },
    profile: { ...data.profile },
    languages: data.languages.map((item) => ({ ...item })),
    education: data.education.map((item) => ({ ...item })),
    experiences: data.experiences.map((item) => ({ ...item })),
    solvedProblems: data.solvedProblems.map((item) => ({ ...item })),
    certifications: [...data.certifications],
    skillGroups: data.skillGroups.map((group) => ({ ...group, items: [...group.items] })),
  };
}

export function normalizeResumeLocale(value: string | null | undefined): ResumeLocale {
  return value === "en" ? "en" : DEFAULT_RESUME_LOCALE;
}

export function getResumeStorageKey(locale: ResumeLocale): string {
  return `${RESUME_STORAGE_KEY}:${locale}`;
}

export function getResumeStorageFallbackKeys(locale: ResumeLocale): string[] {
  return locale === "pt" ? [getResumeStorageKey(locale), RESUME_STORAGE_KEY] : [getResumeStorageKey(locale)];
}

export function getDefaultResumeData(locale: ResumeLocale = DEFAULT_RESUME_LOCALE): ResumeDocument {
  return cloneResumeData(DEFAULT_RESUME_DATA_BY_LOCALE[locale]);
}

export function getResumePreviewCopy(locale: ResumeLocale): ResumePreviewCopy {
  return RESUME_PREVIEW_COPY[locale];
}

export function getResumePdfFilename(locale: ResumeLocale, fullName: string): string {
  const safeName = fullName.trim() || "Samuel Costa";
  return locale === "en" ? `Resume - ${safeName} - English.pdf` : `Currículo - ${safeName} - Português.pdf`;
}

const cleanString = (value: unknown, fallback = ""): string => {
  if (typeof value !== "string") return fallback;
  const trimmed = value.trim();
  return trimmed || fallback;
};

const cleanStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value.map((item) => cleanString(item)).filter(Boolean);
};

const cleanNumber = (value: unknown, fallback: number): number => {
  if (typeof value !== "number" || Number.isNaN(value)) return fallback;
  return value;
};

const cleanBoolean = (value: unknown, fallback: boolean): boolean => {
  if (typeof value !== "boolean") return fallback;
  return value;
};

const cleanPhotoFrameStyle = (value: unknown, fallback: ResumePhotoFrameStyle): ResumePhotoFrameStyle => {
  if (typeof value !== "string") return fallback;
  return RESUME_PHOTO_FRAME_STYLE_OPTIONS.some((option) => option.value === value)
    ? (value as ResumePhotoFrameStyle)
    : fallback;
};

export function normalizeResumeData(value: unknown, locale: ResumeLocale = DEFAULT_RESUME_LOCALE): ResumeDocument {
  const raw = (value && typeof value === "object" ? value : {}) as Partial<ResumeDocument>;
  const fallbackData = DEFAULT_RESUME_DATA_BY_LOCALE[locale];

  return {
    theme: {
      accentColor: cleanString(raw.theme?.accentColor, fallbackData.theme.accentColor),
      sidebarBackground: cleanString(raw.theme?.sidebarBackground, fallbackData.theme.sidebarBackground),
      pageBackground: cleanString(raw.theme?.pageBackground, fallbackData.theme.pageBackground),
      fontScale: Math.min(1.2, Math.max(0.85, cleanNumber(raw.theme?.fontScale, fallbackData.theme.fontScale))),
      sidebarWidth: Math.min(340, Math.max(220, cleanNumber(raw.theme?.sidebarWidth, fallbackData.theme.sidebarWidth))),
      photoFrameStyle: cleanPhotoFrameStyle(raw.theme?.photoFrameStyle, fallbackData.theme.photoFrameStyle),
      uppercaseSkills: cleanBoolean(raw.theme?.uppercaseSkills, fallbackData.theme.uppercaseSkills),
    },
    profile: {
      fullName: cleanString(raw.profile?.fullName, fallbackData.profile.fullName),
      address: cleanString(raw.profile?.address, fallbackData.profile.address),
      phone: cleanString(raw.profile?.phone, fallbackData.profile.phone),
      email: cleanString(raw.profile?.email, fallbackData.profile.email),
      linkedin: cleanString(raw.profile?.linkedin, fallbackData.profile.linkedin),
      github: cleanString(raw.profile?.github, fallbackData.profile.github),
      portfolio: cleanString(raw.profile?.portfolio, fallbackData.profile.portfolio),
      maritalStatus: cleanString(raw.profile?.maritalStatus, fallbackData.profile.maritalStatus),
      nationality: cleanString(raw.profile?.nationality, fallbackData.profile.nationality),
      photoDataUrl: cleanString(raw.profile?.photoDataUrl),
    },
    languages: Array.isArray(raw.languages) && raw.languages.length > 0
      ? raw.languages.map((item) => ({
          name: cleanString(item?.name),
          level: cleanString(item?.level),
        })).filter((item) => item.name || item.level)
      : fallbackData.languages,
    education: Array.isArray(raw.education) && raw.education.length > 0
      ? raw.education.map((item) => ({
          course: cleanString(item?.course),
          conclusion: cleanString(item?.conclusion),
          institution: cleanString(item?.institution),
        })).filter((item) => item.course || item.institution)
      : fallbackData.education,
    experiences: Array.isArray(raw.experiences) && raw.experiences.length > 0
      ? raw.experiences.map((item) => ({
          role: cleanString(item?.role),
          duration: cleanString(item?.duration),
          company: cleanString(item?.company),
          summary: cleanString(item?.summary),
        })).filter((item) => item.role || item.company || item.summary)
      : fallbackData.experiences,
    solvedProblems: Array.isArray(raw.solvedProblems) && raw.solvedProblems.length > 0
      ? raw.solvedProblems.map((item) => ({
          title: cleanString(item?.title),
          context: cleanString(item?.context),
          impact: cleanString(item?.impact),
        })).filter((item) => item.title || item.context || item.impact)
      : fallbackData.solvedProblems,
    certifications: cleanStringArray(raw.certifications).length > 0 ? cleanStringArray(raw.certifications) : fallbackData.certifications,
    skillGroups: Array.isArray(raw.skillGroups) && raw.skillGroups.length > 0
      ? raw.skillGroups.map((item) => ({
          title: cleanString(item?.title),
          items: cleanStringArray(item?.items),
        })).filter((item) => item.title || item.items.length > 0)
      : fallbackData.skillGroups,
  };
}

export function createEmptyEducation(): ResumeEducation {
  return { course: "", conclusion: "", institution: "" };
}

export function createEmptyExperience(): ResumeExperience {
  return { role: "", duration: "", company: "", summary: "" };
}

export function createEmptyLanguage(): ResumeLanguage {
  return { name: "", level: "" };
}

export function createEmptySkillGroup(): ResumeSkillGroup {
  return { title: "", items: [] };
}

export function createEmptySolvedProblem(): ResumeSolvedProblem {
  return { title: "", context: "", impact: "" };
}
