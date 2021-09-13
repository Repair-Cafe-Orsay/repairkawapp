function check_phone(input) {
  var regExp = /^(\+[0-9][- 0-9]+|0[0-9]{9})$/;
  if (input.value.trim() == "" || input.value.match(regExp)) {
   input.setCustomValidity('');
 } else {
   input.setCustomValidity('numéro de téléphone non valide');
 }
}
