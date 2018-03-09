/*
 * 19 Jan 2010, C. Schmidt-Hieber
 *
 * Uses the arduino to control a Picospritzer
 * Send characters to the arduino to open or close
 * the valve:
 * '1' open channel 1
 * '2' open channel 2
 * '3' close channel 1
 * '4' close channel 2
 * '5' open olfactometer valve
 * '6' close olfactometer valve
 * '7' open olfacto2meter valve
 * '8' close olfacto2meter valve
 * '9' open olfacto3meter valve
 * '0' close olfacto3meter valve
 * 'd' broadcast down signal
 * 'e' camera frame capture HI
 * 'f' camera frame capture LO
 * 'r' sense pClamp recording status
 * 'u' broadcast up signal
 * 'w' wipe lick counter
 */

/* extern "C" void __cxa_pure_virtual() {} */

/*
 * Data and clock pin definitions
 */

static const int c1pin = 11; /* Airpuff 1 */
static const int c2pin = 2; /* Airpuff 2 */
static const int lickpin = 3;
static const int campin = 4;
static const int olf1pin = 6;
static const int olf2pin = 8;
static const int olf3pin = 10;
static const int bcpin = 4;
/* static const int epin = 12; */

static const int piezopin = A0;

static const int BAUDRATE = 19200;
int bcstatus = LOW;
int lickcounter = 0;
int lickpiezosum = 0;
int lickstatus = LOW;
int prevstatus = LOW;

// The setup() method runs once, when the sketch starts

void setup()   {                

  // set baud rate
  Serial.begin(BAUDRATE);

  // initialize the digital pin as an output:
  /*pinMode(epin, INPUT);     */
  pinMode(c1pin, OUTPUT);     
  pinMode(c2pin, OUTPUT);
  pinMode(bcpin, OUTPUT);
  pinMode(campin, OUTPUT);
  pinMode(olf1pin, OUTPUT);
  pinMode(olf2pin, OUTPUT);
  pinMode(olf3pin, OUTPUT);

  pinMode(lickpin, INPUT);

  pinMode(piezopin, INPUT);
 
  Serial.write('\n');
}

// the loop() method runs over and over again,
// as long as the Arduino has power
void loop()                     
{
  lickstatus = digitalRead(lickpin);
  if (lickstatus==HIGH && prevstatus==LOW) {
      lickcounter += 1;
  }
  prevstatus = lickstatus;
  lickpiezosum += analogRead(piezopin);
  // Wait for request before doing stuff:
  if ( Serial.available()) {
    char ch = Serial.read();
    switch (ch) {
      case '1':
        digitalWrite(c1pin, HIGH);
        break;
      case '2':
        digitalWrite(c2pin, HIGH);
        break;
      case '3':
        digitalWrite(c1pin, LOW);
        break;
      case '4':
        digitalWrite(c2pin, LOW);
        break;
        /*      case 'r': {
        int ephys = digitalRead(epin);
        if (ephys == HIGH) {
          Serial.write(ephys); 
        } else {
          Serial.write(ephys);
        }
        break;
        }*/
      case 'e': {
        digitalWrite(campin, HIGH);
        break;
      }
      case 'f': {
        digitalWrite(campin, LOW);
        break;
      }
      case 'u': {
        digitalWrite(bcpin, HIGH);
        break;
      }
      case 'd': {
        digitalWrite(bcpin, LOW);
        break;
      }
      case 'w': {
        // transmit lick pin status:
        Serial.println(lickcounter);
        Serial.write(lickcounter);
        Serial.write('\n');
        lickcounter = 0;
        break;
      }
      case 'a': {
        // transmit lick pin status:
        Serial.write(lickpiezosum);
        Serial.write('\n');
        lickpiezosum = 0;
        break;
      }
      case '5':
        digitalWrite(olf1pin, HIGH);
        break;
      case '6':
        digitalWrite(olf1pin, LOW);
        break;
      case '7':
        digitalWrite(olf2pin, HIGH);
        break;
      case '8':
        digitalWrite(olf2pin, LOW);
        break;
      case '9':
        digitalWrite(olf3pin, HIGH);
        break;
      case '0':
        digitalWrite(olf3pin, LOW);
        break;
      default:
        break;
    }
  }

}
