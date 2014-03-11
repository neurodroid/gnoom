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
 * 'r' sense pClamp recording status
 * 'u' broadcast up signal
 * 'd' broadcast down signal
 * 'w' wipe lick counter
 */

extern "C" void __cxa_pure_virtual() {}

/*
 * Data and clock pin definitions
 */
static const int lickpin = 13;
static const int c1pin = 2;
static const int c2pin = 4;
static const int bcpin = 12;
/* static const int epin = 12; */
static const int BAUDRATE = 19200;
int bcstatus = LOW;
int lickcounter = 0;
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

  pinMode(lickpin, INPUT);
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
        Serial.write(lickcounter);
        Serial.write('\n');
        lickcounter = 0;
        break;
      }
      default:
        break;
    }
  }

}
