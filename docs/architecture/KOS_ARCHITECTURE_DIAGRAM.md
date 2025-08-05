# KOS Architecture Diagram

```mermaid
graph TB
    subgraph "Host OS (Windows/Linux)"
        HD[Host Driver<br/>C++]
        HA[Host Applications]
    end

    subgraph "KOS Core"
        subgraph "Security Layer"
            FP[Fingerprint System<br/>Custom Formula + Crypto]
            PWD[Password System<br/>Formula + SHA512]
            RBAC[RBAC Engine<br/>Roles & Groups]
            PERM[Permission Flags<br/>KROOT, KSYSTEM, etc.]
        end

        subgraph "Communication Layer"
            KADCM[KADCM<br/>Host-KOS Bridge]
            TLS[TLS Tunnel<br/>Named Pipes]
            PROTO[Binary Protocol<br/>JSON+YAML]
        end

        subgraph "Application Layer"
            KAIM[KAIM Manager]
            KM[Kernel Module<br/>kaim.ko]
            UD[Userspace Daemon<br/>_kaim]
            SOCK[Unix Socket<br/>/var/run/kaim.sock]
            DEV[Device File<br/>/dev/kaim]
        end

        subgraph "Shell Layer"
            KSH[KOS Shell]
            HIST[Command History<br/>Binary Format]
            TYPO[Typo Correction<br/>Levenshtein]
            ALIAS[Alias System]
            KSUDO[ksudo<br/>Built-in]
        end

        subgraph "Storage"
            SDB[Shadow DB<br/>/etc/kos/shadow]
            FDB[Fingerprint DB<br/>/etc/kos/fingerprints.db]
            PDB[Policy DB<br/>/etc/kos/rbac.json]
            HDB[History DB<br/>/var/lib/kos/history/]
        end
    end

    subgraph "KOS Applications"
        APP1[User Apps]
        APP2[System Services]
        APP3[Admin Tools]
    end

    %% Connections
    HA <--> HD
    HD <--> TLS
    TLS <--> KADCM
    KADCM <--> PROTO

    KADCM --> FP
    KADCM --> RBAC

    APP1 --> SOCK
    APP2 --> SOCK
    APP3 --> SOCK
    SOCK <--> UD
    UD <--> KM
    KM <--> DEV

    KSH --> HIST
    KSH --> TYPO
    KSH --> ALIAS
    KSH --> KSUDO
    KSUDO --> PERM
    KSUDO --> PWD

    FP --> FDB
    PWD --> SDB
    RBAC --> PDB
    PERM --> PDB
    HIST --> HDB

    UD --> PERM
    UD --> RBAC
    KADCM --> PERM

    classDef security fill:#ff6b6b,stroke:#c92a2a,color:#fff
    classDef comm fill:#4dabf7,stroke:#1c7ed6,color:#fff
    classDef app fill:#69db7c,stroke:#37b24d,color:#fff
    classDef shell fill:#ffd43b,stroke:#fab005,color:#000
    classDef storage fill:#e599f7,stroke:#ae3ec9,color:#fff

    class FP,PWD,RBAC,PERM security
    class KADCM,TLS,PROTO,HD comm
    class KAIM,KM,UD,SOCK,DEV app
    class KSH,HIST,TYPO,ALIAS,KSUDO shell
    class SDB,FDB,PDB,HDB storage
```

## Component Flow Diagrams

### Authentication Flow
```mermaid
sequenceDiagram
    participant User
    participant Shell
    participant KAIM
    participant FP as Fingerprint System
    participant PWD as Password System
    participant RBAC

    User->>Shell: Command requiring auth
    Shell->>KAIM: Request elevation
    KAIM->>FP: Verify fingerprint
    FP-->>KAIM: Fingerprint valid
    KAIM->>PWD: Request password
    User->>PWD: Enter password
    PWD->>PWD: Formula + SHA512
    PWD-->>KAIM: Password verified
    KAIM->>RBAC: Check permissions
    RBAC-->>KAIM: Permission granted
    KAIM-->>Shell: Elevation approved
    Shell-->>User: Command executed
```

### Host-KOS Communication Flow
```mermaid
sequenceDiagram
    participant Host
    participant Driver
    participant TLS as TLS Tunnel
    participant KADCM
    participant KOS

    Host->>Driver: Execute command
    Driver->>TLS: Encrypt message
    TLS->>KADCM: Send via pipe
    KADCM->>KADCM: Verify fingerprint
    KADCM->>KOS: Execute command
    KOS-->>KADCM: Command result
    KADCM-->>TLS: Encrypted response
    TLS-->>Driver: Decrypt message
    Driver-->>Host: Return result
```

### Permission Check Flow
```mermaid
graph LR
    A[Application Request] --> B{Check Process Flags}
    B -->|Has Flag| C[Check RBAC Role]
    B -->|No Flag| D[Deny]
    C -->|Role Allows| E[Check Group]
    C -->|Role Denies| D
    E -->|Group Allows| F[Grant Access]
    E -->|Group Denies| D
    F --> G[Log Access]
    D --> H[Log Denial]
```

## Data Flow Architecture

```mermaid
graph TD
    subgraph "Input Layer"
        I1[User Input]
        I2[Host Commands]
        I3[App Requests]
    end

    subgraph "Authentication Layer"
        A1[Fingerprint Verification]
        A2[Password Check]
        A3[Session Management]
    end

    subgraph "Authorization Layer"
        Z1[Permission Flags]
        Z2[RBAC Policies]
        Z3[Group Membership]
    end

    subgraph "Execution Layer"
        E1[Command Execution]
        E2[System Calls]
        E3[Device Access]
    end

    subgraph "Audit Layer"
        L1[Command Logs]
        L2[Access Logs]
        L3[Security Events]
    end

    I1 --> A1
    I2 --> A1
    I3 --> A1
    
    A1 --> A2
    A2 --> A3
    A3 --> Z1
    
    Z1 --> Z2
    Z2 --> Z3
    Z3 --> E1
    
    E1 --> E2
    E2 --> E3
    
    E1 --> L1
    E2 --> L2
    E3 --> L3
```

## State Diagram - Session Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Unauthenticated
    Unauthenticated --> Authenticating: Login attempt
    Authenticating --> Authenticated: Success
    Authenticating --> Unauthenticated: Failure
    Authenticated --> Elevated: ksudo request
    Elevated --> Authenticated: Timeout/Drop
    Authenticated --> Disconnected: Logout
    Disconnected --> [*]
    
    Authenticated --> Suspended: Idle
    Suspended --> Authenticated: Resume
    Suspended --> Disconnected: Timeout
```