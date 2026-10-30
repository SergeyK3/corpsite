// Synthetic reference rows for card regression tests only.
export const educationProgramKindTestRows = [
  ["basic","Основное образование"], ["internship","Интернатура"], ["residency","Резидентура"],
  ["masters","Магистратура"], ["phd","Докторантура (PhD)"], ["other","Другое"], ["aspirantura","Аспирантура"],
].map(([code,name_ru],i)=>({code,name_ru,name_kk:"KK "+name_ru,is_active:true,sort_order:i*10,revision:1}));
