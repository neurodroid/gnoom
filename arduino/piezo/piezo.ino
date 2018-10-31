/*
 * 31 Oct 2018, C. Schmidt-Hieber
 *
 * Uses the arduino to read a piezo lick sensor
 * 
 */

/* extern "C" void __cxa_pure_virtual() {} */

/*
 * Data and clock pin definitions
 */

static const int piezopin = A0;
static const int potpin = A1;
static const int lickpin = 2;
static const unsigned long minlicktime = 50;

static const int BAUDRATE = 19200;

int pot = 0;
int piezo = 0;
unsigned long lastlick = 0;
// The setup() method runs once, when the sketch starts

void setup()   {                

  // set baud rate
  Serial.begin(BAUDRATE);

  analogReadResolution(12);

  // initialize the digital pin as an output:
  /*pinMode(epin, INPUT);     */
  pinMode(piezopin, INPUT);     
  pinMode(potpin, INPUT);
  pinMode(lickpin, OUTPUT);
 
}

// the loop() method runs over and over again,
// as long as the Arduino has power
void loop()                     
{
  pot = analogRead(potpin);
  piezo = analogRead(piezopin);
  if (piezo > pot) {
    Serial.print(pot);
    Serial.print('\t');
    Serial.println(piezo);
    digitalWrite(lickpin, HIGH);
    lastlick = millis();
  } else {
    if (millis()-lastlick > minlicktime) {
      digitalWrite(lickpin, LOW);
      lastlick = 0;
    }
  }

}
